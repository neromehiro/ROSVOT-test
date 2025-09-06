# module/sub/phoneme_mapping.py

"""
日本語歌詞から音素への変換マッピング
"""

# 基本的な日本語音素マッピング
PHONEME_MAP = {
    # あ行
    'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
    'a': 'a', 'i': 'i', 'u': 'u', 'e': 'e', 'o': 'o',
    
    # か行
    'か': 'k a', 'き': 'k i', 'く': 'k u', 'け': 'k e', 'こ': 'k o',
    'が': 'g a', 'ぎ': 'g i', 'ぐ': 'g u', 'げ': 'g e', 'ご': 'g o',
    'ka': 'k a', 'ki': 'k i', 'ku': 'k u', 'ke': 'k e', 'ko': 'k o',
    'ga': 'g a', 'gi': 'g i', 'gu': 'g u', 'ge': 'g e', 'go': 'g o',
    
    # さ行
    'さ': 's a', 'し': 's i', 'す': 's u', 'せ': 's e', 'そ': 's o',
    'ざ': 'z a', 'じ': 'z i', 'ず': 'z u', 'ぜ': 'z e', 'ぞ': 'z o',
    'sa': 's a', 'si': 's i', 'su': 's u', 'se': 's e', 'so': 's o',
    'za': 'z a', 'zi': 'z i', 'zu': 'z u', 'ze': 'z e', 'zo': 'z o',
    
    # た行
    'た': 't a', 'ち': 't i', 'つ': 't u', 'て': 't e', 'と': 't o',
    'だ': 'd a', 'ぢ': 'd i', 'づ': 'd u', 'で': 'd e', 'ど': 'd o',
    'ta': 't a', 'ti': 't i', 'tu': 't u', 'te': 't e', 'to': 't o',
    'da': 'd a', 'di': 'd i', 'du': 'd u', 'de': 'd e', 'do': 'd o',
    
    # な行
    'な': 'n a', 'に': 'n i', 'ぬ': 'n u', 'ね': 'n e', 'の': 'n o',
    'na': 'n a', 'ni': 'n i', 'nu': 'n u', 'ne': 'n e', 'no': 'n o',
    
    # は行
    'は': 'h a', 'ひ': 'h i', 'ふ': 'h u', 'へ': 'h e', 'ほ': 'h o',
    'ば': 'b a', 'び': 'b i', 'ぶ': 'b u', 'べ': 'b e', 'ぼ': 'b o',
    'ぱ': 'p a', 'ぴ': 'p i', 'ぷ': 'p u', 'ぺ': 'p e', 'ぽ': 'p o',
    'ha': 'h a', 'hi': 'h i', 'hu': 'h u', 'he': 'h e', 'ho': 'h o',
    'ba': 'b a', 'bi': 'b i', 'bu': 'b u', 'be': 'b e', 'bo': 'b o',
    'pa': 'p a', 'pi': 'p i', 'pu': 'p u', 'pe': 'p e', 'po': 'p o',
    
    # ま行
    'ま': 'm a', 'み': 'm i', 'む': 'm u', 'め': 'm e', 'も': 'm o',
    'ma': 'm a', 'mi': 'm i', 'mu': 'm u', 'me': 'm e', 'mo': 'm o',
    
    # や行
    'や': 'j a', 'ゆ': 'j u', 'よ': 'j o',
    'ya': 'j a', 'yu': 'j u', 'yo': 'j o',
    
    # ら行
    'ら': 'r a', 'り': 'r i', 'る': 'r u', 'れ': 'r e', 'ろ': 'r o',
    'ra': 'r a', 'ri': 'r i', 'ru': 'r u', 're': 'r e', 'ro': 'r o',
    
    # わ行
    'わ': 'w a', 'ゐ': 'w i', 'ゑ': 'w e', 'を': 'w o', 'ん': 'N',
    'wa': 'w a', 'wi': 'w i', 'we': 'w e', 'wo': 'w o', 'n': 'N',
    
    # 特殊音素
    'っ': 'cl', 'ッ': 'cl',
    'ー': '-', '-': '-',
    ' ': 'Sil', '': 'Sil',
    
    # 拗音
    'きゃ': 'k j a', 'きゅ': 'k j u', 'きょ': 'k j o',
    'しゃ': 's j a', 'しゅ': 's j u', 'しょ': 's j o',
    'ちゃ': 't j a', 'ちゅ': 't j u', 'ちょ': 't j o',
    'にゃ': 'n j a', 'にゅ': 'n j u', 'にょ': 'n j o',
    'ひゃ': 'h j a', 'ひゅ': 'h j u', 'ひょ': 'h j o',
    'みゃ': 'm j a', 'みゅ': 'm j u', 'みょ': 'm j o',
    'りゃ': 'r j a', 'りゅ': 'r j u', 'りょ': 'r j o',
    'ぎゃ': 'g j a', 'ぎゅ': 'g j u', 'ぎょ': 'g j o',
    'じゃ': 'z j a', 'じゅ': 'z j u', 'じょ': 'z j o',
    'びゃ': 'b j a', 'びゅ': 'b j u', 'びょ': 'b j o',
    'ぴゃ': 'p j a', 'ぴゅ': 'p j u', 'ぴょ': 'p j o',
    
    # ローマ字拗音
    'kya': 'k j a', 'kyu': 'k j u', 'kyo': 'k j o',
    'sha': 's j a', 'shu': 's j u', 'sho': 's j o',
    'cha': 't j a', 'chu': 't j u', 'cho': 't j o',
    'nya': 'n j a', 'nyu': 'n j u', 'nyo': 'n j o',
    'hya': 'h j a', 'hyu': 'h j u', 'hyo': 'h j o',
    'mya': 'm j a', 'myu': 'm j u', 'myo': 'm j o',
    'rya': 'r j a', 'ryu': 'r j u', 'ryo': 'r j o',
    'gya': 'g j a', 'gyu': 'g j u', 'gyo': 'g j o',
    'ja': 'z j a', 'ju': 'z j u', 'jo': 'z j o',
    'bya': 'b j a', 'byu': 'b j u', 'byo': 'b j o',
    'pya': 'p j a', 'pyu': 'p j u', 'pyo': 'p j o',
}

def get_phoneme(lyric):
    """
    歌詞から音素を取得
    
    Args:
        lyric (str): 歌詞
        
    Returns:
        str: 音素記号
    """
    if not lyric:
        return 'Sil'
    
    # 直接マッピングがある場合
    if lyric in PHONEME_MAP:
        return PHONEME_MAP[lyric]
    
    # 長い文字列の場合、最初の文字で判定
    if len(lyric) > 1:
        first_char = lyric[0]
        if first_char in PHONEME_MAP:
            return PHONEME_MAP[first_char]
    
    # デフォルトは'a'
    return 'a'

if __name__ == "__main__":
    # テスト用
    test_lyrics = ['さ', 'い', 'た', 'chu', 'ri', 'pu', 'no', 'ha', 'na', 'ga', 'yo', 'あ']
    
    print("音素マッピングテスト:")
    for lyric in test_lyrics:
        phoneme = get_phoneme(lyric)
        print(f"'{lyric}' -> '{phoneme}'")
