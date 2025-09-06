# modules/rosvot_direct_runner.py
import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np

def setup_rosvot_environment():
    """ROSVOT実行環境をセットアップ"""
    # ROSVOTディレクトリに移動
    rosvot_dir = Path(__file__).parent.parent / "ROSVOT"
    original_cwd = os.getcwd()
    os.chdir(rosvot_dir)
    
    # PythonパスにROSVOTディレクトリを追加
    if str(rosvot_dir) not in sys.path:
        sys.path.insert(0, str(rosvot_dir))
    
    return original_cwd, rosvot_dir

def restore_environment(original_cwd):
    """元の環境に戻す"""
    os.chdir(original_cwd)

class TextGridParser:
    """TextGridファイルを解析して音素と単語の情報を抽出するクラス"""
    
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
    
    def get_phoneme_info(self) -> List[Dict]:
        """音素情報を取得"""
        return self.parse_tier("phones")
    
    def get_word_info(self) -> List[Dict]:
        """単語情報を取得"""
        return self.parse_tier("words")

def extract_word_durs(intervals: List[Dict]) -> List[float]:
    """有効な単語の持続時間を抽出"""
    word_durs = []
    
    for interval in intervals:
        text = interval['text']
        duration = interval['duration']
        
        # SP（無音）やAP（息継ぎ）は除外
        # また、異常に長い持続時間（10秒以上）も除外
        if (text not in ['SP', 'AP', ''] and 
            duration > 0.01 and 
            duration < 10.0):  # 10秒以上の異常に長い区間を除外
            word_durs.append(duration)
    
    return word_durs

def create_rosvot_metadata(wav_path: str, word_durs: List[float], output_path: str) -> Dict:
    """ROSVOT用のJSONメタデータを作成"""
    item_name = Path(wav_path).stem.replace(' ', '_').replace('(', '').replace(')', '')
    
    # 絶対パスに変換
    abs_wav_path = os.path.abspath(wav_path)
    
    metadata = [{
        "item_name": item_name,
        "wav_fn": abs_wav_path,
        "word_durs": word_durs
    }]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    return metadata

def run_rosvot_direct(metadata_path: str, output_dir: str) -> bool:
    """ROSVOTを直接実行"""
    original_cwd, rosvot_dir = setup_rosvot_environment()
    
    try:
        # 絶対パスに変換
        abs_metadata_path = os.path.abspath(os.path.join(original_cwd, metadata_path))
        abs_output_dir = os.path.abspath(os.path.join(original_cwd, output_dir))
        
        # ROSVOTのモジュールをインポート
        from inference.rosvot import RosvotInfer
        
        # 引数を設定（sys.argvを模擬）
        sys.argv = [
            'rosvot.py',
            '--metadata', abs_metadata_path,
            '-o', abs_output_dir,
            '--save_plot',
            '--max_frames', '50000',  # フレーム数制限を増加
            '--ds_workers', '0',      # シングルプロセスで実行
            '-v'
        ]
        
        print(f"ROSVOTを直接実行中...")
        print(f"メタデータ: {abs_metadata_path}")
        print(f"出力ディレクトリ: {abs_output_dir}")
        
        # ROSVOTを実行
        rosvot = RosvotInfer()
        results = rosvot.run()
        
        print("ROSVOT実行完了!")
        return True
        
    except Exception as e:
        print(f"ROSVOT実行中にエラーが発生: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        restore_environment(original_cwd)

def main():
    """メイン処理"""
    # ファイルパス設定
    textgrid_path = "dataset/チューリップ/sofa_output/TextGrid/tulip.TextGrid"
    wav_path = "dataset/チューリップ/raw/002_1 VOCALOID  22.wav"
    metadata_path = "dataset/チューリップ/rosvot_input/direct_tulip_metadata.json"
    output_dir = "dataset/チューリップ/rosvot_output_direct"
    
    print("=== 直接実行版TextGridからROSVOT用メタデータ変換 ===")
    
    # 1. TextGridファイルを解析
    print(f"TextGridファイルを解析中: {textgrid_path}")
    parser = TextGridParser(textgrid_path)
    
    # 2. 単語の情報を取得
    word_intervals = parser.get_word_info()
    phoneme_intervals = parser.get_phoneme_info()
    
    print(f"検出された単語数: {len(word_intervals)}")
    print(f"検出された音素数: {len(phoneme_intervals)}")
    
    # 3. 単語の持続時間を抽出
    word_durs = extract_word_durs(word_intervals)
    print(f"有効な単語数: {len(word_durs)}")
    print(f"単語の持続時間（最初の10個）: {word_durs[:10]}")
    
    # 音素情報も表示（参考用）
    phoneme_durs = extract_word_durs(phoneme_intervals)
    phonemes = [interval['text'] for interval in phoneme_intervals if interval['text'] not in ['SP', 'AP', ''] and interval['duration'] > 0.01]
    print(f"有効な音素数: {len(phoneme_durs)}")
    print(f"音素（最初の10個）: {phonemes[:10]}")
    
    # 4. メタデータを作成
    print(f"メタデータを作成中: {metadata_path}")
    os.makedirs(Path(metadata_path).parent, exist_ok=True)
    metadata = create_rosvot_metadata(wav_path, word_durs, metadata_path)
    print(f"メタデータ作成完了: {metadata[0]['item_name']}")
    
    # 5. ROSVOTを直接実行
    print(f"ROSVOTを直接実行中...")
    success = run_rosvot_direct(metadata_path, output_dir)
    
    if success:
        print("\n=== 処理完了 ===")
        print(f"出力ディレクトリ: {output_dir}")
        print("生成されたファイル:")
        
        # 生成されたファイルを確認
        output_path = Path(output_dir)
        if output_path.exists():
            for file_path in output_path.rglob("*"):
                if file_path.is_file():
                    print(f"  {file_path}")
    else:
        print("\n=== エラーで終了 ===")

if __name__ == "__main__":
    main()
