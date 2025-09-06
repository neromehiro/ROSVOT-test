# modules/full_pipeline_sofa_to_midi.py
import json
import re
import os
import sys
import subprocess
import numpy as np
import librosa
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import shutil
import tempfile

class SOFARunner:
    """SOFAを実行してTextGridを生成するクラス"""
    
    def __init__(self, sofa_dir: str = "SOFA"):
        self.sofa_dir = Path(sofa_dir)
        # 絶対パスで指定
        current_dir = Path.cwd()
        self.checkpoint_path = current_dir / self.sofa_dir / "ckpt/SOFA_model_JPN_Ver0.0.2_Beta/japanese-v2.0-45000.ckpt"
        self.dictionary_path = current_dir / self.sofa_dir / "ckpt/SOFA_model_JPN_Ver0.0.2_Beta/japanese-dictionary.txt"
        
    def hiragana_to_phoneme(self, text: str) -> str:
        """ひらがなを音素に変換"""
        # 基本的なひらがな→音素変換マップ
        hiragana_map = {
            'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
            'か': 'k a', 'き': 'k i', 'く': 'k u', 'け': 'k e', 'こ': 'k o',
            'が': 'g a', 'ぎ': 'g i', 'ぐ': 'g u', 'げ': 'g e', 'ご': 'g o',
            'さ': 's a', 'し': 's i', 'す': 's u', 'せ': 's e', 'そ': 's o',
            'ざ': 'z a', 'じ': 'z i', 'ず': 'z u', 'ぜ': 'z e', 'ぞ': 'z o',
            'た': 't a', 'ち': 't i', 'つ': 't u', 'て': 't e', 'と': 't o',
            'だ': 'd a', 'ぢ': 'd i', 'づ': 'd u', 'で': 'd e', 'ど': 'd o',
            'な': 'n a', 'に': 'n i', 'ぬ': 'n u', 'ね': 'n e', 'の': 'n o',
            'は': 'h a', 'ひ': 'h i', 'ふ': 'h u', 'へ': 'h e', 'ほ': 'h o',
            'ば': 'b a', 'び': 'b i', 'ぶ': 'b u', 'べ': 'b e', 'ぼ': 'b o',
            'ぱ': 'p a', 'ぴ': 'p i', 'ぷ': 'p u', 'ぺ': 'p e', 'ぽ': 'p o',
            'ま': 'm a', 'み': 'm i', 'む': 'm u', 'め': 'm e', 'も': 'm o',
            'や': 'y a', 'ゆ': 'y u', 'よ': 'y o',
            'ら': 'r a', 'り': 'r i', 'る': 'r u', 'れ': 'r e', 'ろ': 'r o',
            'わ': 'w a', 'ゐ': 'w i', 'ゑ': 'w e', 'を': 'w o',
            'ん': 'N',
            'ー': ':', # 長音
            'っ': 'cl', # 促音
            ' ': 'SP', # スペース
            '　': 'SP', # 全角スペース
        }
        
        phonemes = []
        words = text.split()
        
        for word_idx, word in enumerate(words):
            if word_idx > 0:
                phonemes.append('SP')  # 単語間に無音を挿入
            
            for char in word:
                if char in hiragana_map:
                    phonemes.append(hiragana_map[char])
                else:
                    # 未知の文字は無視するか、適当な音素に変換
                    print(f"未知の文字: {char}")
                    phonemes.append('a')  # デフォルトで'a'音素
        
        return ' '.join(phonemes)
    
    def create_lab_file(self, text: str, output_path: str) -> bool:
        """テキストから.labファイルを作成"""
        try:
            # ひらがなを音素に変換
            phoneme_text = self.hiragana_to_phoneme(text)
            print(f"変換されたテキスト: {text}")
            print(f"音素列: {phoneme_text}")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(phoneme_text.strip())
            return True
        except Exception as e:
            print(f"labファイル作成エラー: {e}")
            return False
    
    def run_sofa_alignment(self, wav_path: str, text: str, output_dir: str) -> Optional[str]:
        """SOFAを実行して音素アライメントを行う"""
        try:
            # 出力ディレクトリを作成
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # WAVファイルをコピー
            wav_name = Path(wav_path).name
            target_wav = output_path / wav_name
            shutil.copy2(wav_path, target_wav)
            
            # .labファイルを作成
            lab_name = Path(wav_path).stem + ".lab"
            lab_path = output_path / lab_name
            if not self.create_lab_file(text, str(lab_path)):
                return None
            
            # SOFAコマンドを実行（絶対パスで指定）
            cmd = [
                sys.executable, str(self.sofa_dir / "infer.py"),
                "--ckpt", str(self.checkpoint_path),
                "--folder", str(output_path),
                "--g2p", "Dictionary",
                "--dictionary", str(self.dictionary_path),
                "--out_formats", "textgrid",
                "--mode", "force"
            ]
            
            print(f"SOFA実行中: {' '.join(cmd)}")
            print(f"現在のディレクトリ: {Path.cwd()}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                print("SOFA実行完了!")
                # TextGridファイルのパスを返す（TextGridサブディレクトリ内を確認）
                textgrid_path = output_path / f"{Path(wav_path).stem}.TextGrid"
                textgrid_subdir_path = output_path / "TextGrid" / f"{Path(wav_path).stem}.TextGrid"
                
                if textgrid_path.exists():
                    return str(textgrid_path)
                elif textgrid_subdir_path.exists():
                    return str(textgrid_subdir_path)
                else:
                    print(f"TextGridファイルが見つかりません:")
                    print(f"  チェック1: {textgrid_path}")
                    print(f"  チェック2: {textgrid_subdir_path}")
                    return None
            else:
                print(f"SOFAエラー: {result.stderr}")
                print(f"標準出力: {result.stdout}")
                return None
                
        except Exception as e:
            print(f"SOFA実行中にエラー: {e}")
            return None

class TextGridParser:
    """TextGridファイルを解析するクラス"""
    
    def __init__(self, textgrid_path: str):
        self.textgrid_path = textgrid_path
        self.content = self._load_textgrid()
        
    def _load_textgrid(self) -> str:
        """TextGridファイルを読み込み"""
        with open(self.textgrid_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def parse_tier(self, tier_name: str) -> List[Dict]:
        """指定されたtierの情報を抽出"""
        lines = self.content.split('\n')
        in_target_tier = False
        intervals = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # 目的のtierの開始を検出
            if f'name = "{tier_name}"' in line:
                in_target_tier = True
                continue
            
            # 次のtierの開始で終了
            if in_target_tier and line.startswith('item [') and i+1 < len(lines) and 'class = "IntervalTier"' in lines[i+1]:
                break
            
            # intervals内の処理
            if in_target_tier and 'intervals [' in line:
                interval_match = re.search(r'intervals \[(\d+)\]:', line)
                if interval_match:
                    interval_num = int(interval_match.group(1))
                    
                    # xmin, xmax, textを取得
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
    
    def get_word_info(self) -> List[Dict]:
        """単語情報を取得"""
        return self.parse_tier("words")

class ROSVOTRunner:
    """ROSVOTを実行するクラス"""
    
    def __init__(self, rosvot_dir: str = "ROSVOT"):
        self.rosvot_dir = Path(rosvot_dir)
    
    def extract_word_durs(self, intervals: List[Dict]) -> List[float]:
        """有効な単語の持続時間を抽出"""
        word_durs = []
        
        for interval in intervals:
            text = interval['text']
            duration = interval['duration']
            
            # SP（無音）やAP（息継ぎ）は除外
            if text not in ['SP', 'AP', ''] and duration > 0.01:  # 10ms以下は除外
                word_durs.append(duration)
        
        return word_durs
    
    def create_rosvot_metadata(self, wav_path: str, word_durs: List[float], output_path: str) -> Dict:
        """ROSVOT用のJSONメタデータを作成"""
        item_name = Path(wav_path).stem.replace(' ', '_').replace('(', '').replace(')', '')
        
        # WAVファイルパスを絶対パスに変換
        abs_wav_path = os.path.abspath(wav_path)
        
        metadata = [{
            "item_name": item_name,
            "wav_fn": abs_wav_path,
            "word_durs": word_durs
        }]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return metadata
    
    def run_rosvot(self, metadata_path: str, output_dir: str) -> bool:
        """ROSVOTを実行"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 絶対パスに変換
            current_dir = os.getcwd()
            abs_metadata_path = os.path.join(current_dir, metadata_path)
            abs_output_dir = os.path.join(current_dir, output_dir)
            
            # ROSVOTコマンドを実行（絶対パスで指定）
            current_dir = Path.cwd()
            rosvot_script = current_dir / self.rosvot_dir / "inference/rosvot.py"
            
            cmd = [
                sys.executable, str(rosvot_script),
                "--metadata", abs_metadata_path,
                "-o", abs_output_dir,
                "--save_plot",
                "-v"
            ]
            
            print(f"ROSVOT実行中: {' '.join(cmd)}")
            print(f"作業ディレクトリ: {self.rosvot_dir}")
            
            # PYTHONPATHを設定してROSVOTディレクトリを追加
            env = os.environ.copy()
            env['PYTHONPATH'] = str(current_dir / self.rosvot_dir)
            
            result = subprocess.run(
                cmd,
                cwd=str(self.rosvot_dir),
                capture_output=True,
                text=True,
                env=env
            )
            
            if result.returncode == 0:
                print("ROSVOT実行完了!")
                print("標準出力:")
                print(result.stdout)
                return True
            else:
                print("ROSVOTでエラーが発生しました:")
                print("標準エラー:")
                print(result.stderr)
                print("標準出力:")
                print(result.stdout)
                return False
                
        except Exception as e:
            print(f"ROSVOT実行中にエラー: {e}")
            return False

class MIDIConverter:
    """ROSVOTの結果からMIDIファイルを生成するクラス"""
    
    def __init__(self, sample_rate: int = 22050, hop_length: int = 512):
        self.sample_rate = sample_rate
        self.hop_length = hop_length
        
    def load_rosvot_results(self, output_dir: str, item_name: str) -> Optional[Dict]:
        """ROSVOTの結果を読み込み"""
        try:
            # ROSVOTの出力ファイルを探す
            output_path = Path(output_dir)
            
            # ピッチファイルを探す
            pitch_files = list(output_path.glob(f"*{item_name}*pitch*.npy"))
            onset_files = list(output_path.glob(f"*{item_name}*onset*.npy"))
            
            if not pitch_files:
                print(f"ピッチファイルが見つかりません: {output_path}")
                return None
                
            pitch_data = np.load(pitch_files[0])
            onset_data = np.load(onset_files[0]) if onset_files else None
            
            return {
                'pitch': pitch_data,
                'onset': onset_data,
                'sample_rate': self.sample_rate,
                'hop_length': self.hop_length
            }
            
        except Exception as e:
            print(f"ROSVOT結果読み込みエラー: {e}")
            return None
    
    def hz_to_midi_note(self, hz: float) -> int:
        """周波数をMIDIノート番号に変換"""
        if hz <= 0:
            return 0
        return int(69 + 12 * np.log2(hz / 440.0))
    
    def create_midi_from_pitch(self, pitch_data: np.ndarray, onset_data: Optional[np.ndarray], 
                              output_path: str, min_note_duration: float = 0.1) -> bool:
        """ピッチデータからMIDIファイルを作成"""
        try:
            # pretty_midiをインポート（必要に応じてインストール）
            try:
                import pretty_midi
            except ImportError:
                print("pretty_midiがインストールされていません。pip install pretty_midiを実行してください。")
                return False
            
            # MIDIオブジェクトを作成
            midi = pretty_midi.PrettyMIDI()
            instrument = pretty_midi.Instrument(program=0)  # ピアノ
            
            # 時間軸を計算
            time_per_frame = self.hop_length / self.sample_rate
            
            # ピッチデータを処理
            current_note = None
            current_start_time = 0
            
            for i, pitch_hz in enumerate(pitch_data):
                current_time = i * time_per_frame
                
                if pitch_hz > 0:  # 有効なピッチ
                    midi_note = self.hz_to_midi_note(pitch_hz)
                    
                    if current_note is None:
                        # 新しいノートの開始
                        current_note = midi_note
                        current_start_time = current_time
                    elif abs(midi_note - current_note) > 0.5:  # ピッチが変化
                        # 前のノートを終了
                        if current_time - current_start_time >= min_note_duration:
                            note = pretty_midi.Note(
                                velocity=80,
                                pitch=int(current_note),
                                start=current_start_time,
                                end=current_time
                            )
                            instrument.notes.append(note)
                        
                        # 新しいノートを開始
                        current_note = midi_note
                        current_start_time = current_time
                else:
                    # ピッチなし - 現在のノートを終了
                    if current_note is not None:
                        if current_time - current_start_time >= min_note_duration:
                            note = pretty_midi.Note(
                                velocity=80,
                                pitch=int(current_note),
                                start=current_start_time,
                                end=current_time
                            )
                            instrument.notes.append(note)
                        current_note = None
            
            # 最後のノートを処理
            if current_note is not None:
                final_time = len(pitch_data) * time_per_frame
                if final_time - current_start_time >= min_note_duration:
                    note = pretty_midi.Note(
                        velocity=80,
                        pitch=int(current_note),
                        start=current_start_time,
                        end=final_time
                    )
                    instrument.notes.append(note)
            
            # MIDIファイルに楽器を追加
            midi.instruments.append(instrument)
            
            # MIDIファイルを保存
            midi.write(output_path)
            print(f"MIDIファイルを保存しました: {output_path}")
            return True
            
        except Exception as e:
            print(f"MIDI作成エラー: {e}")
            return False

class FullPipeline:
    """完全な自動パイプライン"""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.sofa_runner = SOFARunner()
        self.rosvot_runner = ROSVOTRunner()
        self.midi_converter = MIDIConverter()
    
    def run_full_pipeline(self, wav_path: str, text: str, output_base_dir: str) -> Dict[str, str]:
        """完全なパイプラインを実行"""
        results = {
            'success': False,
            'textgrid_path': None,
            'metadata_path': None,
            'rosvot_output_dir': None,
            'midi_path': None,
            'errors': []
        }
        
        try:
            # 出力ディレクトリを準備
            output_dir = Path(output_base_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            item_name = Path(wav_path).stem.replace(' ', '_').replace('(', '').replace(')', '')
            
            print("=== 完全自動パイプライン開始 ===")
            print(f"入力WAV: {wav_path}")
            print(f"テキスト: {text}")
            print(f"出力ディレクトリ: {output_base_dir}")
            
            # 1. SOFA実行
            print("\n--- ステップ1: SOFA実行 ---")
            sofa_output_dir = output_dir / "sofa_output"
            textgrid_path = self.sofa_runner.run_sofa_alignment(wav_path, text, str(sofa_output_dir))
            
            if not textgrid_path:
                results['errors'].append("SOFA実行に失敗しました")
                return results
            
            results['textgrid_path'] = textgrid_path
            print(f"TextGrid生成完了: {textgrid_path}")
            
            # 2. TextGrid解析
            print("\n--- ステップ2: TextGrid解析 ---")
            parser = TextGridParser(textgrid_path)
            word_intervals = parser.get_word_info()
            
            if not word_intervals:
                results['errors'].append("TextGridから単語情報を抽出できませんでした")
                return results
            
            print(f"単語数: {len(word_intervals)}")
            
            # 3. ROSVOT用メタデータ作成
            print("\n--- ステップ3: ROSVOT用メタデータ作成 ---")
            word_durs = self.rosvot_runner.extract_word_durs(word_intervals)
            
            if not word_durs:
                results['errors'].append("有効な単語の持続時間を抽出できませんでした")
                return results
            
            metadata_path = output_dir / f"{item_name}_metadata.json"
            self.rosvot_runner.create_rosvot_metadata(wav_path, word_durs, str(metadata_path))
            results['metadata_path'] = str(metadata_path)
            print(f"メタデータ作成完了: {metadata_path}")
            print(f"有効な単語数: {len(word_durs)}")
            
            # 4. ROSVOT実行
            print("\n--- ステップ4: ROSVOT実行 ---")
            rosvot_output_dir = output_dir / "rosvot_output"
            rosvot_success = self.rosvot_runner.run_rosvot(str(metadata_path), str(rosvot_output_dir))
            
            if not rosvot_success:
                results['errors'].append("ROSVOT実行に失敗しました")
                return results
            
            results['rosvot_output_dir'] = str(rosvot_output_dir)
            print(f"ROSVOT実行完了: {rosvot_output_dir}")
            
            # 5. MIDI変換
            print("\n--- ステップ5: MIDI変換 ---")
            
            # ROSVOTが既に生成したMIDIファイルを確認
            rosvot_midi_path = Path(rosvot_output_dir) / "midi" / f"{item_name}.mid"
            
            if rosvot_midi_path.exists():
                # ROSVOTが生成したMIDIファイルをコピー
                final_midi_path = output_dir / f"{item_name}.mid"
                shutil.copy2(str(rosvot_midi_path), str(final_midi_path))
                results['midi_path'] = str(final_midi_path)
                print(f"ROSVOTが生成したMIDIファイルを使用: {rosvot_midi_path}")
                print(f"最終MIDIファイル: {final_midi_path}")
            else:
                # フォールバック: 独自のMIDI変換を実行
                print("ROSVOTのMIDIファイルが見つかりません。独自のMIDI変換を実行します。")
                rosvot_results = self.midi_converter.load_rosvot_results(str(rosvot_output_dir), item_name)
                
                if not rosvot_results:
                    results['errors'].append("ROSVOTの結果を読み込めませんでした")
                    return results
                
                midi_path = output_dir / f"{item_name}.mid"
                midi_success = self.midi_converter.create_midi_from_pitch(
                    rosvot_results['pitch'],
                    rosvot_results.get('onset'),
                    str(midi_path)
                )
                
                if not midi_success:
                    results['errors'].append("MIDI変換に失敗しました")
                    return results
                
                results['midi_path'] = str(midi_path)
            results['success'] = True
            
            print("\n=== パイプライン完了 ===")
            print(f"生成されたファイル:")
            print(f"  TextGrid: {results['textgrid_path']}")
            print(f"  メタデータ: {results['metadata_path']}")
            print(f"  ROSVOT出力: {results['rosvot_output_dir']}")
            print(f"  MIDI: {results['midi_path']}")
            
            return results
            
        except Exception as e:
            results['errors'].append(f"パイプライン実行中にエラー: {e}")
            print(f"パイプラインエラー: {e}")
            return results

def main():
    """メイン処理"""
    # サンプル設定
    wav_path = "dataset/チューリップ/raw/001_1 VOCALOID  tyu-rti.wav"
    text = "さいた さいた チューリップの はなが ならんだ ならんだ あか しろ きいろ どの はなみても きれいだな"
    output_base_dir = "dataset/チューリップ/pipeline_output"
    
    print("=== SOFA → TextGrid → ROSVOT → MIDI 完全自動パイプライン ===")
    print(f"入力WAV: {wav_path}")
    print(f"テキスト: {text}")
    print(f"出力ディレクトリ: {output_base_dir}")
    
    # パイプラインを実行
    pipeline = FullPipeline()
    results = pipeline.run_full_pipeline(wav_path, text, output_base_dir)
    
    if results['success']:
        print("\n✅ パイプライン成功!")
        print(f"MIDIファイル: {results['midi_path']}")
    else:
        print("\n❌ パイプライン失敗:")
        for error in results['errors']:
            print(f"  - {error}")

if __name__ == "__main__":
    main()
