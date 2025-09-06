# modules/audio_melody_pipeline.py

import json
import re
import os
import shutil
from pathlib import Path
import subprocess
from typing import List, Dict, Optional, Tuple

class AudioMelodyPipeline:
    """SOFAとROSVOTを統合した音声メロディライン抽出パイプライン"""
    
    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name
        self.dataset_path = Path(f"dataset/{dataset_name}")
        self.raw_path = self.dataset_path / "raw"
        self.sofa_output_path = self.dataset_path / "sofa_output"
        self.rosvot_input_path = self.dataset_path / "rosvot_input"
        self.rosvot_output_path = self.dataset_path / "rosvot_output"
        
        # ディレクトリを作成
        self._create_directories()
    
    def _create_directories(self):
        """必要なディレクトリを作成"""
        directories = [
            self.raw_path,
            self.sofa_output_path,
            self.rosvot_input_path,
            self.rosvot_output_path / "midi",
            self.rosvot_output_path / "plot",
            self.rosvot_output_path / "npy"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def parse_textgrid(self, textgrid_path: Path) -> List[Dict]:
        """TextGridファイルを解析して単語の持続時間を抽出"""
        with open(textgrid_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        in_words_tier = False
        intervals = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # words層の開始を検出
            if 'name = "words"' in line:
                in_words_tier = True
                continue
            
            # 次のtierの開始で終了
            if in_words_tier and line.startswith('item [') and i+1 < len(lines) and 'class = "IntervalTier"' in lines[i+1]:
                break
            
            # intervals内の処理
            if in_words_tier and 'intervals [' in line:
                interval_match = re.search(r'intervals \[(\d+)\]:', line)
                if interval_match:
                    xmin = None
                    xmax = None
                    text = None
                    
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith('intervals ['):
                        if 'xmin =' in lines[j]:
                            xmin = float(lines[j].split('=')[1].strip())
                        elif 'xmax =' in lines[j]:
                            xmax = float(lines[j].split('=')[1].strip())
                        elif 'text =' in lines[j]:
                            text = lines[j].split('=')[1].strip().strip('"')
                        j += 1
                    
                    if xmin is not None and xmax is not None and text is not None:
                        intervals.append({
                            'xmin': xmin,
                            'xmax': xmax,
                            'text': text,
                            'duration': xmax - xmin
                        })
        
        return intervals
    
    def extract_word_durs(self, intervals: List[Dict]) -> List[float]:
        """intervalsから有効な単語の持続時間を抽出（SPは除外）"""
        word_durs = []
        
        for interval in intervals:
            text = interval['text']
            duration = interval['duration']
            
            # SP（無音）やAP（息継ぎ）は除外
            if text not in ['SP', 'AP', ''] and duration > 0.01:  # 10ms以下は除外
                word_durs.append(duration)
        
        return word_durs
    
    def create_rosvot_metadata(self, wav_path: Path, word_durs: List[float]) -> Dict:
        """ROSVOT用のJSONメタデータを作成"""
        item_name = wav_path.stem.replace(' ', '_').replace('(', '').replace(')', '')
        
        metadata = [{
            "item_name": item_name,
            "wav_fn": str(wav_path),
            "word_durs": word_durs
        }]
        
        return metadata
    
    def run_sofa(self, wav_path: Path, text_path: Path) -> bool:
        """SOFAを実行してタイムスタンプを生成"""
        print(f"SOFAを実行中: {wav_path.name}")
        
        # SOFAの入力用ディレクトリを準備
        sofa_input_path = Path("SOFA/segments/temp")
        sofa_input_path.mkdir(parents=True, exist_ok=True)
        
        # ファイル名を安全な形式に変換
        safe_name = re.sub(r'[^\w\-_]', '_', wav_path.stem)
        
        # ファイルをコピー
        shutil.copy(wav_path, sofa_input_path / f"{safe_name}.wav")
        
        # テキストを読み込んで.labファイルとして保存
        with open(text_path, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        
        # 簡単な音素変換（実際にはより複雑な処理が必要）
        phonemes = self._convert_to_phonemes(text)
        
        with open(sofa_input_path / f"{safe_name}.lab", 'w', encoding='utf-8') as f:
            f.write(phonemes)
        
        # SOFAを実行
        cmd = [
            "python", "SOFA/infer.py",
            "--ckpt", "SOFA/ckpt/SOFA_model_JPN_Ver0.0.2_Beta/japanese-v2.0-45000.ckpt",
            "--folder", str(sofa_input_path),
            "--out_formats", "textgrid,htk",
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
            
            if result.returncode == 0:
                print("SOFA実行完了")
                
                # 結果をコピー
                for result_format in ["TextGrid", "htk"]:
                    result_path = sofa_input_path / result_format
                    if result_path.exists():
                        dest_path = self.sofa_output_path / result_format
                        if dest_path.exists():
                            shutil.rmtree(dest_path)
                        shutil.copytree(result_path, dest_path)
                        print(f"{result_format}の結果を{dest_path}にコピーしました")
                
                # 一時ファイルをクリーンアップ
                shutil.rmtree(sofa_input_path)
                return True
            else:
                print(f"SOFAでエラーが発生: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"SOFA実行中にエラー: {e}")
            return False
    
    def _convert_to_phonemes(self, text: str) -> str:
        """簡単な音素変換（実際にはより高度な処理が必要）"""
        # 基本的な変換のみ実装
        phonemes = text.replace('さいた', 's a i t a')
        phonemes = phonemes.replace('チューリップ', 'ch u u r i p p u')
        phonemes = phonemes.replace('はなが', 'h a n a g a')
        return phonemes
    
    def run_rosvot(self, metadata_path: Path) -> bool:
        """ROSVOTを実行してメロディラインを抽出"""
        print("ROSVOTを実行中...")
        
        # ROSVOTディレクトリからの相対パスに変換
        relative_metadata_path = Path("..") / metadata_path
        relative_output_path = Path("..") / self.rosvot_output_path
        
        # ROSVOTを実行
        cmd = [
            'python', 'inference/rosvot.py',
            '--metadata', str(relative_metadata_path),
            '-o', str(relative_output_path),
            '--save_plot',
            '-v'
        ]
        
        try:
            # 環境変数を設定
            env = os.environ.copy()
            env['PYTHONPATH'] = '.'
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd='ROSVOT',
                env=env
            )
            
            if result.returncode == 0:
                print("ROSVOT実行完了!")
                return True
            else:
                print(f"ROSVOTでエラーが発生: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"ROSVOT実行中にエラー: {e}")
            return False
    
    def process_dataset(self, use_existing_sofa: bool = True) -> bool:
        """データセット全体を処理"""
        print(f"=== {self.dataset_name} データセット処理開始 ===")
        
        # 入力ファイルを確認
        wav_files = list(self.raw_path.glob("*.wav"))
        txt_files = list(self.raw_path.glob("*.txt"))
        
        if not wav_files:
            print("エラー: 音声ファイルが見つかりません")
            return False
        
        if not txt_files:
            print("エラー: テキストファイルが見つかりません")
            return False
        
        wav_path = wav_files[0]
        txt_path = txt_files[0]
        
        print(f"音声ファイル: {wav_path}")
        print(f"テキストファイル: {txt_path}")
        
        # 1. SOFAでタイムスタンプ生成（既存のものがない場合）
        textgrid_files = list(self.sofa_output_path.glob("TextGrid/*.TextGrid"))
        
        if not use_existing_sofa or not textgrid_files:
            print("SOFAでタイムスタンプを生成中...")
            if not self.run_sofa(wav_path, txt_path):
                print("SOFAの実行に失敗しました")
                return False
            textgrid_files = list(self.sofa_output_path.glob("TextGrid/*.TextGrid"))
        
        if not textgrid_files:
            print("エラー: TextGridファイルが見つかりません")
            return False
        
        textgrid_path = textgrid_files[0]
        print(f"TextGridファイル: {textgrid_path}")
        
        # 2. TextGridからword_dursを抽出
        print("TextGridを解析中...")
        intervals = self.parse_textgrid(textgrid_path)
        word_durs = self.extract_word_durs(intervals)
        
        print(f"抽出された単語数: {len(word_durs)}")
        
        # 3. ROSVOT用メタデータを作成
        # ROSVOTディレクトリからの相対パスで音声ファイルパスを設定
        relative_wav_path = Path("..") / wav_path
        metadata = self.create_rosvot_metadata(relative_wav_path, word_durs)
        metadata_path = self.rosvot_input_path / "metadata.json"
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"メタデータ作成完了: {metadata_path}")
        
        # 4. ROSVOTでメロディライン抽出
        if not self.run_rosvot(metadata_path):
            print("ROSVOTの実行に失敗しました")
            return False
        
        print(f"\n=== 処理完了 ===")
        print(f"出力ディレクトリ: {self.dataset_path}")
        print("生成されたファイル:")
        
        # 生成されたファイルを表示
        for file_path in self.dataset_path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                print(f"  {file_path.relative_to(self.dataset_path)}")
        
        return True

def main():
    """メイン関数"""
    # チューリップデータセットを処理
    pipeline = AudioMelodyPipeline("チューリップ")
    
    # 既存のSOFAデータを使用して処理
    success = pipeline.process_dataset(use_existing_sofa=True)
    
    if success:
        print("\n全ての処理が完了しました！")
    else:
        print("\n処理中にエラーが発生しました。")

if __name__ == "__main__":
    main()
