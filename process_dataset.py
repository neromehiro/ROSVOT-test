import os
import shutil
import subprocess
from pathlib import Path
import re

# 日本語をローマ字に変換する辞書
HIRAGANA_TO_ROMAJI = {
    'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
    'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
    'が': 'ga', 'ぎ': 'gi', 'ぐ': 'gu', 'げ': 'ge', 'ご': 'go',
    'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
    'ざ': 'za', 'じ': 'ji', 'ず': 'zu', 'ぜ': 'ze', 'ぞ': 'zo',
    'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
    'だ': 'da', 'ぢ': 'ji', 'づ': 'zu', 'で': 'de', 'ど': 'do',
    'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
    'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
    'ば': 'ba', 'び': 'bi', 'ぶ': 'bu', 'べ': 'be', 'ぼ': 'bo',
    'ぱ': 'pa', 'ぴ': 'pi', 'ぷ': 'pu', 'ぺ': 'pe', 'ぽ': 'po',
    'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
    'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
    'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
    'わ': 'wa', 'ゐ': 'wi', 'ゑ': 'we', 'を': 'wo', 'ん': 'n',
    # カタカナ
    'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
    'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
    'ガ': 'ga', 'ギ': 'gi', 'グ': 'gu', 'ゲ': 'ge', 'ゴ': 'go',
    'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
    'ザ': 'za', 'ジ': 'ji', 'ズ': 'zu', 'ゼ': 'ze', 'ゾ': 'zo',
    'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
    'ダ': 'da', 'ヂ': 'ji', 'ヅ': 'zu', 'デ': 'de', 'ド': 'do',
    'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'ノ': 'no',
    'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
    'バ': 'ba', 'ビ': 'bi', 'ブ': 'bu', 'ベ': 'be', 'ボ': 'bo',
    'パ': 'pa', 'ピ': 'pi', 'プ': 'pu', 'ペ': 'pe', 'ポ': 'po',
    'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'モ': 'mo',
    'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
    'ラ': 'ra', 'リ': 'ri', 'ル': 'ru', 'レ': 're', 'ロ': 'ro',
    'ワ': 'wa', 'ヰ': 'wi', 'ヱ': 'we', 'ヲ': 'wo', 'ン': 'n',
    # 長音記号
    'ー': '',
    # 特殊な組み合わせ
    'きゃ': 'kya', 'きゅ': 'kyu', 'きょ': 'kyo',
    'しゃ': 'sha', 'しゅ': 'shu', 'しょ': 'sho',
    'ちゃ': 'cha', 'ちゅ': 'chu', 'ちょ': 'cho',
    'にゃ': 'nya', 'にゅ': 'nyu', 'にょ': 'nyo',
    'ひゃ': 'hya', 'ひゅ': 'hyu', 'ひょ': 'hyo',
    'みゃ': 'mya', 'みゅ': 'myu', 'みょ': 'myo',
    'りゃ': 'rya', 'りゅ': 'ryu', 'りょ': 'ryo',
    'ぎゃ': 'gya', 'ぎゅ': 'gyu', 'ぎょ': 'gyo',
    'じゃ': 'ja', 'じゅ': 'ju', 'じょ': 'jo',
    'びゃ': 'bya', 'びゅ': 'byu', 'びょ': 'byo',
    'ぴゃ': 'pya', 'ぴゅ': 'pyu', 'ぴょ': 'pyo',
    # カタカナ版
    'キャ': 'kya', 'キュ': 'kyu', 'キョ': 'kyo',
    'シャ': 'sha', 'シュ': 'shu', 'ショ': 'sho',
    'チャ': 'cha', 'チュ': 'chu', 'チョ': 'cho',
    'ニャ': 'nya', 'ニュ': 'nyu', 'ニョ': 'nyo',
    'ヒャ': 'hya', 'ヒュ': 'hyu', 'ヒョ': 'hyo',
    'ミャ': 'mya', 'ミュ': 'myu', 'ミョ': 'myo',
    'リャ': 'rya', 'リュ': 'ryu', 'リョ': 'ryo',
    'ギャ': 'gya', 'ギュ': 'gyu', 'ギョ': 'gyo',
    'ジャ': 'ja', 'ジュ': 'ju', 'ジョ': 'jo',
    'ビャ': 'bya', 'ビュ': 'byu', 'ビョ': 'byo',
    'ピャ': 'pya', 'ピュ': 'pyu', 'ピョ': 'pyo',
}

# 特殊な単語の変換
SPECIAL_WORDS = {
    'チューリップ': 'ch u u r i p p u',
    'ちゅーりっぷ': 'ch u u r i p p u',
}

def convert_to_phonemes(text):
    """日本語テキストを音素レベルのローマ字に変換"""
    # 特殊な単語を先に処理
    for word, phonemes in SPECIAL_WORDS.items():
        text = text.replace(word, phonemes)
    
    result = []
    i = 0
    while i < len(text):
        # 2文字の組み合わせをチェック（拗音など）
        if i < len(text) - 1:
            two_char = text[i:i+2]
            if two_char in HIRAGANA_TO_ROMAJI:
                phonemes = HIRAGANA_TO_ROMAJI[two_char]
                if phonemes:  # 空文字でない場合
                    result.extend(phonemes.split())
                i += 2
                continue
        
        # 1文字の変換
        char = text[i]
        if char in HIRAGANA_TO_ROMAJI:
            phonemes = HIRAGANA_TO_ROMAJI[char]
            if phonemes:  # 空文字でない場合
                result.extend(phonemes.split())
        elif char == ' ' or char == '　':
            # スペースは無視
            pass
        elif char.isalpha():
            # 英字はそのまま追加
            result.append(char.lower())
        
        i += 1
    
    return ' '.join(result)

def process_dataset(dataset_path, model_ckpt_path=None):
    """
    データセットフォルダを処理
    """
    dataset_path = Path(dataset_path)
    
    if not dataset_path.exists():
        print(f"エラー: フォルダ {dataset_path} が見つかりません")
        return
    
    # wavとtxtファイルを検索（サブフォルダも含む）
    wav_files = list(dataset_path.glob("**/*.wav"))
    txt_files = list(dataset_path.glob("**/*.txt"))
    
    print(f"{len(wav_files)}個のwavファイルと{len(txt_files)}個のtxtファイルを発見しました")
    
    if not wav_files:
        print("wavファイルが見つかりません")
        return
    
    # segments フォルダを作成
    segments_path = Path("SOFA/segments/processed")
    segments_path.mkdir(parents=True, exist_ok=True)
    
    # 各wavファイルを処理
    for wav_file in wav_files:
        base_name = wav_file.stem
        # ファイル名から特殊文字を除去してSOFA用の名前を作成
        safe_name = re.sub(r'[^\w\-_]', '_', base_name)
        
        # 対応するテキストファイルを探す
        # まず同じディレクトリで同名のtxtファイルを探す
        txt_file = wav_file.parent / f"{base_name}.txt"
        if not txt_file.exists():
            # 同じディレクトリのtext.txtを探す
            txt_file = wav_file.parent / "text.txt"
        if not txt_file.exists():
            # データセットルートのtext.txtを探す
            txt_file = dataset_path / "text.txt"
        
        if txt_file.exists():
            # wavファイルをコピー
            shutil.copy(wav_file, segments_path / f"{safe_name}.wav")
            
            # テキストを読み込んで変換
            with open(txt_file, 'r', encoding='utf-8') as f:
                text = f.read().strip()
            
            # 音素に変換
            phonemes = convert_to_phonemes(text)
            
            # .labファイルとして保存
            with open(segments_path / f"{safe_name}.lab", 'w', encoding='utf-8') as f:
                f.write(phonemes)
            
            print(f"処理完了: {base_name}")
            print(f"  元のテキスト: {text}")
            print(f"  音素変換: {phonemes}")
        else:
            print(f"警告: {base_name}に対応するテキストファイルが見つかりません")
    
    # SOFAの推論を実行
    if model_ckpt_path and Path(model_ckpt_path).exists():
        print("SOFAの推論を実行中...")
        # SOFAディレクトリ内で実行するため、相対パスを調整
        segments_path_from_sofa = Path("../") / segments_path
        model_ckpt_from_sofa = Path("../") / model_ckpt_path
        
        cmd = [
            "python", "infer.py",
            "--ckpt", str(model_ckpt_from_sofa),
            "--folder", str(segments_path_from_sofa),
            "--out_formats", "textgrid,htk",
        ]
        
        try:
            # SOFAディレクトリで実行
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="SOFA")
            if result.returncode == 0:
                print("SOFA推論が完了しました")
                
                # 結果を元のフォルダにコピー
                for result_format in ["TextGrid", "htk"]:
                    result_path = segments_path / result_format
                    if result_path.exists():
                        dest_path = dataset_path / result_format
                        if dest_path.exists():
                            shutil.rmtree(dest_path)
                        shutil.copytree(result_path, dest_path)
                        print(f"{result_format}の結果を{dest_path}にコピーしました")
            else:
                print(f"SOFA推論でエラーが発生しました: {result.stderr}")
        except Exception as e:
            print(f"SOFA実行中にエラーが発生しました: {e}")
    else:
        if model_ckpt_path:
            print(f"警告: モデルファイル {model_ckpt_path} が見つかりません")
        print("モデルファイルが指定されていないため、SOFA推論をスキップします")
        print("手動でSOFAを実行する場合:")
        print(f"python SOFA/infer.py --folder {segments_path} --out_formats textgrid,htk")

def main():
    # 直書きのパス
    path = "dataset/チューリップ"
    
    # 日本語モデルファイルのパス
    model_ckpt = "SOFA/ckpt/SOFA_model_JPN_Ver0.0.2_Beta/japanese-v2.0-45000.ckpt"
    
    print("データセット処理を開始します...")
    process_dataset(path, model_ckpt)
    print("処理完了!")

if __name__ == "__main__":
    main()
