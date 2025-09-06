import json
import re
import os
from pathlib import Path
import subprocess

def parse_textgrid(textgrid_path):
    """TextGridファイルを解析して単語の持続時間を抽出"""
    with open(textgrid_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # words層を探す
    words_section = None
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
        if in_words_tier and line.startswith('item [') and 'class = "IntervalTier"' in lines[i+1]:
            break
        
        # intervals内の処理
        if in_words_tier and 'intervals [' in line:
            # interval番号を取得
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

def extract_word_durs(intervals):
    """intervalsから有効な単語の持続時間を抽出（SPは除外）"""
    word_durs = []
    
    for interval in intervals:
        text = interval['text']
        duration = interval['duration']
        
        # SP（無音）やAP（息継ぎ）は除外
        if text not in ['SP', 'AP', ''] and duration > 0.01:  # 10ms以下は除外
            word_durs.append(duration)
    
    return word_durs

def create_rosvot_metadata(wav_path, word_durs, output_path):
    """ROSVOT用のJSONメタデータを作成"""
    # ファイル名から拡張子を除去してitem_nameを作成
    item_name = Path(wav_path).stem.replace(' ', '_').replace('(', '').replace(')', '')
    
    metadata = [{
        "item_name": item_name,
        "wav_fn": str(wav_path),
        "word_durs": word_durs
    }]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    return metadata

def run_rosvot(metadata_path, output_dir):
    """ROSVOTを実行"""
    # 出力ディレクトリを作成
    os.makedirs(output_dir, exist_ok=True)
    
    # ROSVOTコマンドを構築
    cmd = [
        'python', 'ROSVOT/inference/rosvot.py',
        '--metadata', metadata_path,
        '-o', output_dir,
        '--save_plot',
        '-v'
    ]
    
    print(f"ROSVOTを実行中: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        
        if result.returncode == 0:
            print("ROSVOT実行完了!")
            print("標準出力:")
            print(result.stdout)
        else:
            print("ROSVOTでエラーが発生しました:")
            print("標準エラー:")
            print(result.stderr)
            print("標準出力:")
            print(result.stdout)
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"ROSVOT実行中にエラーが発生: {e}")
        return False

def main():
    # ファイルパス設定
    textgrid_path = "チューリップ/TextGrid/002_1_VOCALOID__22.TextGrid"
    wav_path = "チューリップ/002_1 VOCALOID  22.wav"
    metadata_path = "tulip_metadata.json"
    output_dir = "output_with_timestamp"
    
    print("=== TextGridからROSVOT用メタデータ変換 ===")
    
    # 1. TextGridファイルを解析
    print(f"TextGridファイルを解析中: {textgrid_path}")
    intervals = parse_textgrid(textgrid_path)
    print(f"検出されたintervals数: {len(intervals)}")
    
    # 2. word_dursを抽出
    word_durs = extract_word_durs(intervals)
    print(f"抽出された単語数: {len(word_durs)}")
    print(f"単語の持続時間: {word_durs[:10]}...")  # 最初の10個を表示
    
    # 3. ROSVOT用メタデータを作成
    print(f"メタデータを作成中: {metadata_path}")
    metadata = create_rosvot_metadata(wav_path, word_durs, metadata_path)
    print(f"メタデータ作成完了: {metadata[0]['item_name']}")
    
    # 4. ROSVOTを実行
    print(f"ROSVOTを実行中...")
    success = run_rosvot(metadata_path, output_dir)
    
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
