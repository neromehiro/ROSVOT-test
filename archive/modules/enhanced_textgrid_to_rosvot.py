# modules/enhanced_textgrid_to_rosvot.py
import json
import re
import os
from pathlib import Path
import subprocess
import numpy as np
from typing import List, Dict, Tuple, Optional

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

class PhonemeAnalyzer:
    """音素情報を分析するクラス"""
    
    # 日本語音素の分類
    VOWELS = {'a', 'i', 'u', 'e', 'o'}
    CONSONANTS = {
        's', 't', 'k', 'n', 'h', 'm', 'r', 'w', 'g', 'z', 'j', 'b', 'd', 'p', 'f', 'v',
        'ch', 'sh', 'ts', 'ky', 'gy', 'ny', 'hy', 'by', 'py', 'my', 'ry'
    }
    SPECIAL_TOKENS = {'SP', 'AP', ''}  # SP: 無音, AP: 息継ぎ
    
    @classmethod
    def classify_phoneme(cls, phoneme: str) -> str:
        """音素を分類"""
        if phoneme in cls.SPECIAL_TOKENS:
            return 'silence'
        elif phoneme in cls.VOWELS:
            return 'vowel'
        elif phoneme in cls.CONSONANTS:
            return 'consonant'
        else:
            return 'unknown'
    
    @classmethod
    def is_valid_phoneme(cls, phoneme: str, min_duration: float = 0.01) -> bool:
        """有効な音素かどうか判定"""
        return (phoneme not in cls.SPECIAL_TOKENS and 
                phoneme != '' and 
                min_duration > 0.01)

class ROSVOTDataProcessor:
    """ROSVOT用のデータを処理するクラス"""
    
    def __init__(self, hop_size: int = 512, sample_rate: int = 22050):
        self.hop_size = hop_size
        self.sample_rate = sample_rate
        
    def extract_word_durs(self, intervals: List[Dict]) -> List[float]:
        """有効な単語の持続時間を抽出"""
        word_durs = []
        
        for interval in intervals:
            text = interval['text']
            duration = interval['duration']
            
            # SP（無音）やAP（息継ぎ）は除外
            if PhonemeAnalyzer.is_valid_phoneme(text, duration):
                word_durs.append(duration)
        
        return word_durs
    
    def extract_phoneme_features(self, phoneme_intervals: List[Dict]) -> Dict:
        """音素情報から特徴量を抽出"""
        phoneme_features = {
            'phonemes': [],
            'phoneme_durs': [],
            'phoneme_types': [],
            'vowel_positions': [],
            'consonant_positions': []
        }
        
        current_time = 0.0
        
        for interval in phoneme_intervals:
            phoneme = interval['text']
            duration = interval['duration']
            
            if PhonemeAnalyzer.is_valid_phoneme(phoneme, duration):
                phoneme_type = PhonemeAnalyzer.classify_phoneme(phoneme)
                
                phoneme_features['phonemes'].append(phoneme)
                phoneme_features['phoneme_durs'].append(duration)
                phoneme_features['phoneme_types'].append(phoneme_type)
                
                # 音素の位置を記録（フレーム単位）
                start_frame = int(current_time * self.sample_rate / self.hop_size)
                end_frame = int((current_time + duration) * self.sample_rate / self.hop_size)
                
                if phoneme_type == 'vowel':
                    phoneme_features['vowel_positions'].append((start_frame, end_frame))
                elif phoneme_type == 'consonant':
                    phoneme_features['consonant_positions'].append((start_frame, end_frame))
            
            current_time += duration
        
        return phoneme_features
    
    def create_phoneme_boundary_mask(self, phoneme_intervals: List[Dict], total_duration: float) -> np.ndarray:
        """音素境界のマスクを作成"""
        total_frames = int(total_duration * self.sample_rate / self.hop_size)
        boundary_mask = np.zeros(total_frames)
        
        current_time = 0.0
        for interval in phoneme_intervals:
            if PhonemeAnalyzer.is_valid_phoneme(interval['text'], interval['duration']):
                # 音素境界の位置をマーク
                boundary_frame = int(current_time * self.sample_rate / self.hop_size)
                if boundary_frame < total_frames:
                    boundary_mask[boundary_frame] = 1.0
            
            current_time += interval['duration']
        
        return boundary_mask

def create_enhanced_rosvot_metadata(wav_path: str, word_durs: List[float], 
                                  phoneme_features: Dict, output_path: str) -> Dict:
    """拡張されたROSVOT用のJSONメタデータを作成"""
    item_name = Path(wav_path).stem.replace(' ', '_').replace('(', '').replace(')', '')
    
    metadata = [{
        "item_name": item_name,
        "wav_fn": str(wav_path),
        "word_durs": word_durs,
        # 音素情報を追加
        "phoneme_info": {
            "phonemes": phoneme_features['phonemes'],
            "phoneme_durs": phoneme_features['phoneme_durs'],
            "phoneme_types": phoneme_features['phoneme_types'],
            "vowel_positions": phoneme_features['vowel_positions'],
            "consonant_positions": phoneme_features['consonant_positions']
        }
    }]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    return metadata

def run_enhanced_rosvot(metadata_path: str, output_dir: str) -> bool:
    """拡張されたROSVOTを実行"""
    os.makedirs(output_dir, exist_ok=True)
    
    # 絶対パスに変換
    current_dir = os.getcwd()
    abs_metadata_path = os.path.join(current_dir, metadata_path)
    abs_output_dir = os.path.join(current_dir, output_dir)
    
    # run_rosvot.shスクリプトを使用
    cmd = [
        'bash', 'run_rosvot.sh',
        '--metadata', abs_metadata_path,
        '-o', abs_output_dir,
        '--save_plot',
        '-v'
    ]
    
    print(f"拡張ROSVOTを実行中: {' '.join(cmd)}")
    print(f"作業ディレクトリ: ROSVOT")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='ROSVOT')
        
        if result.returncode == 0:
            print("拡張ROSVOT実行完了!")
            print("標準出力:")
            print(result.stdout)
        else:
            print("拡張ROSVOTでエラーが発生しました:")
            print("標準エラー:")
            print(result.stderr)
            print("標準出力:")
            print(result.stdout)
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"拡張ROSVOT実行中にエラーが発生: {e}")
        return False

def main():
    """メイン処理"""
    # ファイルパス設定
    textgrid_path = "dataset/チューリップ/sofa_output/TextGrid/tulip.TextGrid"
    wav_path = "dataset/チューリップ/raw/002_1 VOCALOID  22.wav"  # 実際のwavファイルパス
    metadata_path = "dataset/チューリップ/rosvot_input/enhanced_tulip_metadata.json"
    output_dir = "dataset/チューリップ/rosvot_output_enhanced"
    
    print("=== 拡張TextGridからROSVOT用メタデータ変換 ===")
    
    # 1. TextGridファイルを解析
    print(f"TextGridファイルを解析中: {textgrid_path}")
    parser = TextGridParser(textgrid_path)
    
    # 2. 音素と単語の情報を取得
    phoneme_intervals = parser.get_phoneme_info()
    word_intervals = parser.get_word_info()
    
    print(f"検出された音素数: {len(phoneme_intervals)}")
    print(f"検出された単語数: {len(word_intervals)}")
    
    # 3. データ処理
    processor = ROSVOTDataProcessor()
    
    # 単語の持続時間を抽出
    word_durs = processor.extract_word_durs(word_intervals)
    print(f"有効な単語数: {len(word_durs)}")
    print(f"単語の持続時間（最初の10個）: {word_durs[:10]}")
    
    # 音素特徴量を抽出
    phoneme_features = processor.extract_phoneme_features(phoneme_intervals)
    print(f"有効な音素数: {len(phoneme_features['phonemes'])}")
    print(f"音素（最初の10個）: {phoneme_features['phonemes'][:10]}")
    print(f"音素タイプ（最初の10個）: {phoneme_features['phoneme_types'][:10]}")
    
    # 4. 拡張メタデータを作成
    print(f"拡張メタデータを作成中: {metadata_path}")
    os.makedirs(Path(metadata_path).parent, exist_ok=True)
    metadata = create_enhanced_rosvot_metadata(wav_path, word_durs, phoneme_features, metadata_path)
    print(f"拡張メタデータ作成完了: {metadata[0]['item_name']}")
    
    # 5. ROSVOTを実行
    print(f"拡張ROSVOTを実行中...")
    success = run_enhanced_rosvot(metadata_path, output_dir)
    
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
