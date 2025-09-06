# module/sub/a_create_timestamps.py
########## [Script Entry Point] パス設定ブロック - 開始 ##########
import sys
import os

if __name__ == "__main__" and __package__ is None:
    # スクリプトが直接実行された場合、プロジェクトのルートディレクトリをsys.pathに追加
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "../../")) # 2階層下の場合
    sys.path.insert(0, project_root)
########## [Script Entry Point] パス設定ブロック - 終了 ##########

import json
import re
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# かな→SOFA辞書ローマ字変換用のマッピング
YOON_MAP = {
    "きゃ":"kya","きゅ":"kyu","きょ":"kyo",
    "ぎゃ":"gya","ぎゅ":"gyu","ぎょ":"gyo",
    "しゃ":"sha","しゅ":"shu","しょ":"sho",
    "じゃ":"ja","じゅ":"ju","じょ":"jo",
    "ちゃ":"cha","ちゅ":"chu","ちょ":"cho",
    "にゃ":"nya","にゅ":"nyu","にょ":"nyo",
    "ひゃ":"hya","ひゅ":"hyu","ひょ":"hyo",
    "びゃ":"bya","びゅ":"byu","びょ":"byo",
    "ぴゃ":"pya","ぴゅ":"pyu","ぴょ":"pyo",
    "みゃ":"mya","みゅ":"myu","みょ":"myo",
    "りゃ":"rya","りゅ":"ryu","りょ":"ryo",
    "ふぁ":"fa","ふぃ":"fi","ふぇ":"fe","ふぉ":"fo",
}

BASIC_MAP = {
    "あ":"a","い":"i","う":"u","え":"e","お":"o",
    "か":"ka","き":"ki","く":"ku","け":"ke","こ":"ko",
    "が":"ga","ぎ":"gi","ぐ":"gu","げ":"ge","ご":"go",
    "さ":"sa","し":"shi","す":"su","せ":"se","そ":"so",
    "ざ":"za","じ":"ji","ず":"zu","ぜ":"ze","ぞ":"zo",
    "た":"ta","ち":"chi","つ":"tsu","て":"te","と":"to",
    "だ":"da","ぢ":"ji","づ":"zu","で":"de","ど":"do",
    "な":"na","に":"ni","ぬ":"nu","ね":"ne","の":"no",
    "は":"ha","ひ":"hi","ふ":"fu","へ":"he","ほ":"ho",
    "ば":"ba","び":"bi","ぶ":"bu","べ":"be","ぼ":"bo",
    "ぱ":"pa","ぴ":"pi","ぷ":"pu","ぺ":"pe","ぽ":"po",
    "ま":"ma","み":"mi","む":"mu","め":"me","も":"mo",
    "や":"ya","ゆ":"yu","よ":"yo",
    "ら":"ra","り":"ri","る":"ru","れ":"re","ろ":"ro",
    "わ":"wa","を":"wo","ん":"N",
}

def kata_to_hira(text: str) -> str:
    """カタカナをひらがなに変換"""
    result = ""
    for ch in text:
        if "ァ" <= ch <= "ヴ":
            result += chr(ord(ch) - 0x60)
        else:
            result += ch
    return result

def kana_to_sofa_tokens(text: str) -> List[str]:
    """かな文字列をSOFA辞書ローマ字トークンに変換（モーラ単位で分割）"""
    # 前処理：スペース正規化、カタカナ→ひらがな
    text = re.sub(r"\s+", " ", text.strip())
    text = kata_to_hira(text)
    
    tokens = []
    
    # 単語ごとに処理（スペースで区切られた部分）
    for word in text.split(" "):
        if not word:
            continue
            
        i = 0
        while i < len(word):
            ch = word[i]
            
            # 促音「っ」→ cl
            if ch == "っ":
                tokens.append("cl")
                i += 1
                continue
                
            # 長音「ー」→ 直前トークンの母音を繰り返し
            if ch == "ー":
                if tokens and re.search(r"[aiueo]$", tokens[-1]):
                    # 直前トークンの末尾母音を1モーラ追加
                    tokens.append(tokens[-1][-1])
                i += 1
                continue
                
            # 拗音処理（ゃゅょ）
            if i + 1 < len(word) and word[i + 1] in "ゃゅょ":
                pair = word[i:i + 2]
                if pair in YOON_MAP:
                    tokens.append(YOON_MAP[pair])
                    i += 2
                    continue
                    
            # 基本かな処理
            if ch in BASIC_MAP:
                tokens.append(BASIC_MAP[ch])
                i += 1
                continue
                
            # その他の文字は無視
            print(f"未対応文字をスキップ: {ch}")
            i += 1
    
    return tokens  # モーラだけの配列を返す（スペースは入れない）

def load_dictionary_keys(dict_path: str) -> set:
    """辞書ファイルからキーを読み込む"""
    keys = set()
    try:
        with open(dict_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '\t' in line:
                    key = line.split('\t', 1)[0].strip()
                    keys.add(key)
    except Exception as e:
        print(f"辞書読み込みエラー: {e}")
    return keys

def check_dictionary_coverage(tokens: List[str], dict_keys: set) -> List[str]:
    """トークンの辞書カバレッジをチェック"""
    unknown_tokens = [token for token in tokens if token not in dict_keys]
    return unknown_tokens

class SOFARunner:
    """SOFAを実行してTextGridを生成するクラス"""
    
    def __init__(self, sofa_dir: str = "SOFA"):
        self.sofa_dir = Path(sofa_dir)
        # 絶対パスで指定
        current_dir = Path.cwd()
        self.checkpoint_path = current_dir / self.sofa_dir / "ckpt/SOFA_model_JPN_Ver0.0.2_Beta/japanese-v2.0-45000.ckpt"
        self.dictionary_path = current_dir / self.sofa_dir / "ckpt/SOFA_model_JPN_Ver0.0.2_Beta/japanese-dictionary.txt"
        
    def create_lab_file(self, text: str, output_path: str) -> bool:
        """かな→SOFA辞書ローマ字に変換して.labファイルを作成"""
        try:
            # かな→ローマ字トークンに変換
            tokens = kana_to_sofa_tokens(text)
            token_string = " ".join(tokens)
            
            print(f"入力テキスト: {text}")
            print(f"変換後トークン: {token_string}")
            
            # 辞書カバレッジをチェック
            dict_keys = load_dictionary_keys(str(self.dictionary_path))
            unknown_tokens = check_dictionary_coverage(tokens, dict_keys)
            
            print(f"辞書登録済みキー数: {len(dict_keys)}")
            print(f"生成トークン数: {len(tokens)}")
            print(f"未知トークン: {unknown_tokens[:10]}")  # 最初の10個だけ表示
            
            if unknown_tokens:
                print(f"⚠️ 辞書に未登録のトークンが {len(unknown_tokens)} 個あります")
            else:
                print("✅ 全トークンが辞書に登録されています")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(token_string + "\n")
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
                "--out_formats", "textgrid,trans",
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
                # TextGridファイルを再帰的に検索
                textgrid_files = list(output_path.rglob("*.TextGrid"))
                
                if textgrid_files:
                    # 最初に見つかったTextGridファイルを返す
                    found_textgrid = textgrid_files[0]
                    print(f"TextGridファイルを発見: {found_textgrid}")
                    return str(found_textgrid)
                else:
                    print(f"TextGridファイルが見つかりません:")
                    print(f"  出力ディレクトリ: {output_path}")
                    print(f"  ディレクトリ内容:")
                    for item in output_path.rglob("*"):
                        print(f"    {item}")
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
    
    def get_phoneme_info(self) -> List[Dict]:
        """音素情報を取得"""
        return self.parse_tier("phones")
    
    def get_word_info(self) -> List[Dict]:
        """単語情報を取得"""
        return self.parse_tier("words")

def create_timestamps(wav_path: str, lyrics_text: str) -> Tuple[Dict, Optional[str]]:
    """
    音声ファイルと歌詞データからタイムスタンプを作成
    
    Args:
        wav_path: 音声ファイルのパス
        lyrics_text: 歌詞テキスト
        
    Returns:
        timestamps: タイムスタンプ情報の辞書
        textgrid_path: 生成されたTextGridファイルのパス（一時的にコピーされたもの）
    """
    try:
        # 一時ディレクトリでSOFAを実行
        with tempfile.TemporaryDirectory() as temp_dir:
            # SOFA実行
            sofa_runner = SOFARunner()
            textgrid_path = sofa_runner.run_sofa_alignment(wav_path, lyrics_text, temp_dir)
            
            if not textgrid_path:
                raise Exception("SOFA実行に失敗しました")
            
            # TextGrid解析
            parser = TextGridParser(textgrid_path)
            phoneme_intervals = parser.get_phoneme_info()
            word_intervals = parser.get_word_info()
            
            # タイムスタンプ情報を構築
            timestamps = {
                "words": [],
                "phonemes": [],
                "word_durations": []
            }
            
            # 単語情報を処理
            for interval in word_intervals:
                text = interval['text']
                start = interval['xmin']
                end = interval['xmax']
                duration = interval['duration']
                
                timestamps["words"].append((start, end, text))
                
                # SP（無音）やAP（息継ぎ）以外の有効な単語の持続時間を記録
                if text not in ['SP', 'AP', ''] and duration > 0.01:
                    timestamps["word_durations"].append(duration)
            
            # 音素情報を処理
            for interval in phoneme_intervals:
                phoneme = interval['text']
                start = interval['xmin']
                end = interval['xmax']
                
                timestamps["phonemes"].append((start, end, phoneme))
            
            print(f"タイムスタンプ作成完了:")
            print(f"  単語数: {len(timestamps['words'])}")
            print(f"  音素数: {len(timestamps['phonemes'])}")
            print(f"  有効な単語持続時間数: {len(timestamps['word_durations'])}")
            
            # TextGridファイルを一時的にコピー（一時ディレクトリが削除される前に）
            if textgrid_path and Path(textgrid_path).exists():
                # 一時的なコピー先を作成
                temp_textgrid = tempfile.NamedTemporaryFile(suffix='.TextGrid', delete=False)
                temp_textgrid.close()
                shutil.copy2(textgrid_path, temp_textgrid.name)
                return timestamps, temp_textgrid.name
            else:
                return timestamps, None
            
    except Exception as e:
        print(f"タイムスタンプ作成エラー: {e}")
        return {}, None

import pykakasi

def main():
    """メイン処理"""
    # 対象ディレクトリを設定
    target_dir = "dataset/チューリップ/raw"
    wav_files = list(Path(target_dir).glob("*.wav"))
    txt_files = list(Path(target_dir).glob("*.txt"))

    if not wav_files or not txt_files:
        print(f"❌ WAVまたはTXTファイルが見つかりません: {target_dir}")
        return

    wav_path = str(wav_files[0])
    text_path = str(txt_files[0])

    # text.txt を読み込み、pykakasiでひらがなに変換
    kakasi = pykakasi.kakasi()
    kakasi.setMode("J", "H")  # 漢字→ひらがな
    kakasi.setMode("K", "H")  # カタカナ→ひらがな
    kakasi.setMode("H", "H")  # ひらがなはそのまま
    conv = kakasi.getConverter()

    raw_text = Path(text_path).read_text(encoding="utf-8").strip()
    lyrics_text = conv.do(raw_text)

    print("=== 音声ファイルと歌詞からタイムスタンプ作成 ===")
    print(f"入力WAV: {wav_path}")
    print(f"元テキスト: {raw_text}")
    print(f"ひらがな変換後: {lyrics_text}")
    
    # タイムスタンプを作成
    timestamps, textgrid_path = create_timestamps(wav_path, lyrics_text)
    
    if timestamps:
        print("\n✅ タイムスタンプ作成成功!")
        
        # 中間生成物を保存（if __name__ == "__main__"時のみ）
        item_name = Path(wav_path).stem.replace(' ', '_').replace('(', '').replace(')', '')
        output_dir = Path("output") / item_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # JSONファイルを保存
        timestamps_path = output_dir / "a_timestamps.json"
        with open(timestamps_path, 'w', encoding='utf-8') as f:
            json.dump(timestamps, f, indent=2, ensure_ascii=False)
        
        # TextGridファイルを保存
        if textgrid_path and Path(textgrid_path).exists():
            textgrid_output_path = output_dir / "a_textgrid.TextGrid"
            shutil.copy2(textgrid_path, textgrid_output_path)
            print(f"📁 TextGrid成果物を保存: {textgrid_output_path}")
        else:
            print(f"⚠️  TextGridファイルが見つかりません: {textgrid_path}")
        
        print(f"📁 JSON成果物を保存: {timestamps_path}")
        print(f"📊 単語持続時間（最初の10個）: {timestamps['word_durations'][:10]}")
        print(f"🔗 次のステップ: python module/sub/b_convert_to_rosvot.py")
        
        return timestamps
    else:
        print("\n❌ タイムスタンプ作成失敗")
        return None

if __name__ == "__main__":
    main()
