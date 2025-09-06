#!/usr/bin/env python3
"""
テキスト形式をVPRファイルに変換するツール
"""

import json
import zipfile
import argparse
import re
import sys
import os
from fractions import Fraction

# 現在のディレクトリをパスに追加
sys.path.append(os.path.dirname(__file__))
from phoneme_mapping import get_phoneme

# 音名からMIDI番号への変換テーブル
NOTE_TO_MIDI = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4,
    'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8,
    'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
}

def note_to_midi(note_name, octave=4):
    """音名をMIDI番号に変換"""
    if note_name not in NOTE_TO_MIDI:
        return 60  # デフォルトはC4
    return (octave + 1) * 12 + NOTE_TO_MIDI[note_name]

def fraction_to_ticks(fraction_str, ticks_per_quarter=480):
    """分数文字列をtick数に変換（厳密化版）"""
    if fraction_str == "0":
        return 0
    try:
        if '/' in fraction_str:
            num, den = map(int, fraction_str.split('/'))
            # ここで厳密化：四分音符 × (num/den)
            ticks = (num * ticks_per_quarter) / den
            return int(round(ticks))
        else:
            return int(round(int(fraction_str) * ticks_per_quarter))
    except:
        return ticks_per_quarter  # フォールバック

def get_ticks_per_bar(numer, denom, ticks_per_quarter=480):
    """1小節のtick数を計算"""
    # 4/4拍子の場合: 4 * 480 = 1920 ticks
    # 3/4拍子の場合: 3 * 480 = 1440 ticks
    return int(numer * ticks_per_quarter * 4 / denom)

def parse_metadata(text):
    """テキストからメタデータを抽出"""
    import re
    
    # HTMLコメントからメタデータを抽出
    metadata = {'start_tick': 0, 'ticks_per_quarter': 480, 'time_sig': (4, 4), 'tempo': 120, 'phonemes': {}, 'block_cycle': None, 'block_anchors': None}
    
    comment_match = re.search(r'<!--\s*(.+?)\s*-->', text)
    if comment_match:
        comment_content = comment_match.group(1)
        
        # @start_tick=値 の形式で抽出
        start_tick_match = re.search(r'@start_tick=(\d+)', comment_content)
        if start_tick_match:
            metadata['start_tick'] = int(start_tick_match.group(1))
        
        # @ticks_per_quarter=値 の形式で抽出
        tpq_match = re.search(r'@ticks_per_quarter=(\d+)', comment_content)
        if tpq_match:
            metadata['ticks_per_quarter'] = int(tpq_match.group(1))
        
        # @time_sig=分子/分母 の形式で抽出
        time_sig_match = re.search(r'@time_sig=(\d+)/(\d+)', comment_content)
        if time_sig_match:
            metadata['time_sig'] = (int(time_sig_match.group(1)), int(time_sig_match.group(2)))
        
        # @tempo=値 の形式で抽出
        tempo_match = re.search(r'@tempo=(\d+(?:\.\d+)?)', comment_content)
        if tempo_match:
            metadata['tempo'] = float(tempo_match.group(1))
        
        # @phonemes=値 の形式で抽出
        phonemes_match = re.search(r'@phonemes=([^@]*)', comment_content)
        if phonemes_match:
            phonemes_str = phonemes_match.group(1).strip()
            phonemes_dict = {}
            if phonemes_str:
                for item in phonemes_str.split('|'):
                    if ':' in item:
                        key, value = item.split(':', 1)
                        phonemes_dict[key] = value
            metadata['phonemes'] = phonemes_dict
        
        # @block_cycle=4
        bc_match = re.search(r'@block_cycle=(\d+)', comment_content)
        if bc_match:
            metadata['block_cycle'] = int(bc_match.group(1))
        # @block_anchors=49440,53280,...
        ba_match = re.search(r'@block_anchors=([0-9,\s]+)', comment_content)
        if ba_match:
            anchors = [int(x) for x in ba_match.group(1).replace(' ','').split(',') if x.strip().isdigit()]
            metadata['block_anchors'] = anchors if anchors else None
    
    return metadata

def parse_text_table(text, time_sig=(4, 4), ticks_per_quarter=480, start_tick_offset=0, phonemes_dict=None):
    """テキストテーブルをパース（4の倍数バー固定アンカー対応版）"""
    lines = text.strip().split('\n')

    # テーブル行の抽出（新形式：A, B, C...の行）
    data_lines = []
    for line in lines:
        if line.strip().startswith('|') and not line.strip().startswith('|---') and '曲名' not in line:
            data_lines.append(line.strip())

    ticks_per_bar = get_ticks_per_bar(time_sig[0], time_sig[1], ticks_per_quarter)
    half_bar = ticks_per_bar // 2
    
    notes = []
    prev_midi = 60  # 近傍オクターブ推定用
    
    # メタデータ（ブロックアンカー）を取得
    metadata = parse_metadata(text)
    anchors = metadata.get('block_anchors')
    block_cycle = metadata.get('block_cycle') or 4

    # アンカーが無い場合は4の倍数バーで推定
    if not anchors:
        # 最初のコンテンツを含む4の倍数バーを推定
        content_start_bar = start_tick_offset // ticks_per_bar
        first_anchor_bar = ((content_start_bar + block_cycle - 1) // block_cycle) * block_cycle
        # 必要な分だけアンカーを生成
        num_blocks = (len(data_lines) + block_cycle - 1) // block_cycle
        anchors = []
        for i in range(num_blocks):
            anchors.append((first_anchor_bar + i * block_cycle) * ticks_per_bar)

    # 行を処理（ブロックモード：A,B,C,Dを周期解釈）
    for row_index, line in enumerate(data_lines):
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if len(cells) < 3:
            continue
        bar_label = cells[0]
        first_half = cells[1]
        second_half = cells[2]

        # 周回とブロック内オフセット
        cycle_idx = row_index // block_cycle
        label_idx = {"A":0,"B":1,"C":2,"D":3}.get(bar_label, (row_index % block_cycle))
        
        if cycle_idx < len(anchors):
            base = anchors[cycle_idx] + label_idx * ticks_per_bar
        else:
            # アンカーが不足している場合は、最後のアンカーから継続
            if anchors:
                last_anchor = anchors[-1]
                extra_cycles = cycle_idx - len(anchors) + 1
                base = last_anchor + (extra_cycles * block_cycle + label_idx) * ticks_per_bar
            else:
                base = start_tick_offset + row_index * ticks_per_bar

        # 前半セル
        cell0_start = base
        cell0_end = cell0_start + half_bar
        notes_0, prev_midi = parse_cell(first_half, cell0_start, cell0_end,
                                        ticks_per_quarter, prev_midi, phonemes_dict)
        notes.extend(notes_0)

        # 後半セル
        cell1_start = cell0_end
        cell1_end = cell1_start + half_bar
        notes_1, prev_midi = parse_cell(second_half, cell1_start, cell1_end,
                                        ticks_per_quarter, prev_midi, phonemes_dict)
        notes.extend(notes_1)
    
    # ★重複ノート正規化を適用してから結合
    notes = normalize_monophonic(sorted(notes, key=lambda n: (n['pos'], n['number'])))
    return merge_ties(notes)

def parse_cell(cell_text, cell_start, cell_end, ticks_per_quarter, prev_midi, phonemes_dict):
    """セル内の音符をパース（ブロック原点/負オフセット対応。休符は追加せず時間だけ進める）"""
    notes = []
    cursor = cell_start
    
    if cell_text.strip():  # セルに内容がある場合のみパース
        elements = [elem.strip() for elem in cell_text.split(',') if elem.strip()]
        
        for element in elements:
            es = element.strip()
            # 1) 明示： [lyr]dur@-off Pitch
            m_exp = re.match(r'\[([^\]]*)\]([0-9/]+)@-([0-9/]+)\s+([A-G](?:[#b])?(?:-?\d+)?)$', es)
            # 2) 省略： [lyr]-off Pitch （duration=off）
            m_pick = re.match(r'\[([^\]]*)\]-([0-9/]+)\s+([A-G](?:[#b])?(?:-?\d+)?)$', es)
            # 3) 通常： [lyr]dur Pitch
            m_norm = re.match(r'\[([^\]]*)\]([0-9/]+)(?:\s+([A-G](?:[#b])?(?:-?\d+)?))?$', es)

            if m_exp:
                lyric, dur_s, off_s, note_name = m_exp.groups()
                duration = fraction_to_ticks(dur_s, ticks_per_quarter)
                offset  = fraction_to_ticks(off_s, ticks_per_quarter)
                start_pos = max(0, cell_start - offset)
                midi_number = compute_midi_with_octave(note_name, prev_midi)
                prev_midi = midi_number
                phoneme = get_phoneme_for_note(lyric, start_pos, phonemes_dict)
                notes.append({'pos': start_pos,'duration': duration,'number': midi_number,'lyric': (lyric if lyric!='-' else 'ー'),'phoneme': phoneme,'velocity':64})
                # 負オフセットはセル時間を進めない
                continue

            if m_pick:
                lyric, off_s, note_name = m_pick.groups()
                offset = fraction_to_ticks(off_s, ticks_per_quarter)
                duration = offset  # 省略規則：dur=off
                start_pos = max(0, cell_start - offset)
                midi_number = compute_midi_with_octave(note_name, prev_midi)
                prev_midi = midi_number
                phoneme = get_phoneme_for_note(lyric, start_pos, phonemes_dict)
                notes.append({'pos': start_pos,'duration': duration,'number': midi_number,'lyric': (lyric if lyric!='-' else 'ー'),'phoneme': phoneme,'velocity':64})
                continue

            if m_norm:
                lyric = m_norm.group(1)
                duration_str = m_norm.group(2)
                note_name = m_norm.group(3)
                duration = fraction_to_ticks(duration_str, ticks_per_quarter)
                
                if lyric == ' ':  # 休符の場合
                    cursor += duration
                elif note_name and lyric not in ['']:  # 通常の音符またはタイ
                    midi_number = compute_midi_with_octave(note_name, prev_midi)
                    prev_midi = midi_number
                    phoneme = get_phoneme_for_note(lyric, cursor, phonemes_dict)
                    notes.append({
                        'pos': cursor,
                        'duration': duration,
                        'number': midi_number,
                        'lyric': lyric if lyric != '-' else 'ー',
                        'phoneme': phoneme,
                        'velocity': 64
                    })
                    cursor += duration
                else:
                    cursor += duration
            # いずれにも当たらない→無視

    # セル終端まで時間だけ進む（休符は生成しない）
    return notes, prev_midi

def compute_midi_with_octave(note_name, prev_midi):
    """音名からMIDI番号を計算（近傍オクターブ推定付き）"""
    import re as _re
    m = _re.fullmatch(r'([A-G](?:[#b])?)(-?\d+)?', note_name)
    if m:
        pc, octv = m.group(1), m.group(2)
        if octv is not None:
            # オクターブ指定あり
            return note_to_midi(pc, int(octv))
        else:
            # オクターブ指定なし：前のノートに最も近いオクターブを選択
            base_midi = NOTE_TO_MIDI[pc]
            candidates = []
            for oct in range(0, 10):  # オクターブ0-9を候補
                candidate_midi = (oct + 1) * 12 + base_midi
                if 0 <= candidate_midi <= 127:  # MIDI範囲内
                    distance = abs(candidate_midi - prev_midi)
                    candidates.append((distance, candidate_midi))
            # 最も近いものを選択
            candidates.sort()
            return candidates[0][1] if candidates else 60
    else:
        return note_to_midi(note_name, 4)  # フォールバック

def get_phoneme_for_note(lyric, pos, phonemes_dict):
    """音符の音素を取得（メタデータ優先、なければマッピングから）"""
    phoneme = None
    if phonemes_dict:
        # メタデータから音素を検索
        phoneme_key = f"{lyric}@{pos}"
        phoneme = phonemes_dict.get(phoneme_key)
    
    if not phoneme:
        # マッピングから音素を取得
        phoneme = get_phoneme(lyric)
    
    return phoneme

def normalize_monophonic(notes, eps=3):
    """始点優先・前ノートをクリップして重複ノートを正規化"""
    if not notes:
        return notes
    
    notes = sorted(notes, key=lambda n: (n['pos'], -n.get('duration', 0), 
                                         -n.get('velocity', 64), -n.get('number', 60)))
    out = []
    
    for n in notes:
        if out:
            prev = out[-1]
            prev_end = prev['pos'] + prev['duration']
            if n['pos'] < prev_end:
                overlap = prev_end - n['pos']
                if overlap <= eps:
                    # 微小重なりは許容（前ノートを維持）
                    pass
                else:
                    # 大きな重なりは前ノートをクリップ
                    prev['duration'] = max(0, n['pos'] - prev['pos'])
                    if prev['duration'] == 0:
                        out.pop()  # 完全に被ったら削除
        out.append(n)
    
    return [x for x in out if x.get('duration', 0) > 0]

def merge_ties(notes):
    """[-]/長音片を前ノートへ結合してノート数を減らす"""
    if not notes:
        return notes
    
    notes = sorted(notes, key=lambda n: (n['pos'], n['number']))
    out = []
    
    for n in notes:
        # 前のノートと同じ音高・連続・タイ記号なら結合
        if (out and n['lyric'] in ('-', 'ー') and
            n['number'] == out[-1]['number'] and
            n['pos'] == out[-1]['pos'] + out[-1]['duration']):
            # 前のノートの長さを延長（歌詞は前のノートのものを保持）
            out[-1]['duration'] += n['duration']
        else:
            # 通常のノートとして追加（伸ばし棒も含む）
            out.append(n)
    
    return out

def parse_music_data(music_data, start_pos=0, ticks_per_bar=1920, phonemes_dict=None):
    """音楽データ文字列をパースして音符リストを返す（近傍オクターブ推定付き）"""
    notes = []
    current_pos = start_pos
    prev_midi = 60  # C4をデフォルトとして記憶
    
    # バーごとに分割
    bars = music_data.split(' | ')
    
    for bar_idx, bar in enumerate(bars):
        bar_start_pos = current_pos  # この小節の開始位置を記録
        used = 0  # この小節で消費したtick数を追跡
        
        # バー内の要素をパース
        elements = [elem.strip() for elem in bar.split(',') if elem.strip()]
        
        for element in elements:
            # 正規表現で [歌詞]長さ 音名 の形式をパース（オクターブ付きも対応）
            match = re.match(r'\[([^\]]*)\]([0-9/]+)(?:\s+([A-G](?:[#b])?(?:-?\d+)?))?', element.strip())
            
            if match:
                lyric = match.group(1)
                duration_str = match.group(2)
                note_name = match.group(3)
                
                duration = fraction_to_ticks(duration_str)
                used += duration  # 消費tick数を累積
                
                if note_name and lyric not in [' ', '']:  # 休符でない場合
                    # C / C# / Db / C4 / C#4 / Db4 を解釈
                    import re as _re
                    m = _re.fullmatch(r'([A-G](?:[#b])?)(-?\d+)?', note_name)
                    if m:
                        pc, octv = m.group(1), m.group(2)
                        if octv is not None:
                            # オクターブ指定あり
                            midi_number = note_to_midi(pc, int(octv))
                        else:
                            # オクターブ指定なし：前のノートに最も近いオクターブを選択
                            base_midi = NOTE_TO_MIDI[pc]
                            candidates = []
                            for oct in range(0, 10):  # オクターブ0-9を候補
                                candidate_midi = (oct + 1) * 12 + base_midi
                                if 0 <= candidate_midi <= 127:  # MIDI範囲内
                                    distance = abs(candidate_midi - prev_midi)
                                    candidates.append((distance, candidate_midi))
                            # 最も近いものを選択
                            candidates.sort()
                            midi_number = candidates[0][1] if candidates else 60
                    else:
                        midi_number = note_to_midi(note_name, 4)  # フォールバック
                    
                    # 次回のために記憶
                    prev_midi = midi_number
                    
                    # 音素を取得（メタデータから優先、なければマッピングから）
                    phoneme = None
                    if phonemes_dict:
                        # メタデータから音素を検索
                        phoneme_key = f"{lyric}@{current_pos}"
                        phoneme = phonemes_dict.get(phoneme_key)
                    
                    if not phoneme:
                        # マッピングから音素を取得
                        phoneme = get_phoneme(lyric)
                    
                    notes.append({
                        'pos': current_pos,
                        'duration': duration,
                        'number': midi_number,
                        'lyric': lyric if lyric != '-' else 'ー',  # タイの場合は長音記号
                        'phoneme': phoneme,
                        'velocity': 64
                    })
                
                current_pos += duration
        
        # ★重要：小節ごとに必ず ticks_per_bar だけ時間を進める
        # 足りない分を暗黙の休符として前進（空小節でも時間が保たれる）
        if used < ticks_per_bar:
            shortage = ticks_per_bar - used
            current_pos += shortage
            print(f"bar {bar_idx}: used={used}/{ticks_per_bar}, shortage={shortage}, empty={not elements}")
        elif used > ticks_per_bar:
            print(f"bar {bar_idx}: used={used}/{ticks_per_bar}, overflow={used - ticks_per_bar}")
        else:
            print(f"bar {bar_idx}: used={used}/{ticks_per_bar}, perfect match")
    
    return notes

def create_vpr_data(notes, title="Converted Song", tempo=120, time_sig=(4, 4), part_pos=0):
    """音符データからVPRのJSONデータを作成"""
    
    # 最後のノートの終了位置を計算
    if notes:
        max_end_pos = max(note['pos'] + note['duration'] for note in notes)
        duration = max_end_pos - part_pos
    else:
        duration = 7680
    
    # 基本構造を作成（オリジナルに合わせて修正）
    vpr_data = {
        "version": {
            "major": 5,
            "minor": 1,
            "revision": 0
        },
        "vender": "Yamaha Corporation",
        "title": title,
        "masterTrack": {
            "samplingRate": 44100,
            "loop": {
                "isEnabled": False,
                "begin": 0,
                "end": duration
            },
            "tempo": {
                "isFolded": False,
                "height": 0.0,
                "global": {
                    "isEnabled": True,
                    "value": int(tempo * 100)
                },
                "events": [
                    {
                        "pos": 0,
                        "value": int(tempo * 100)
                    }
                ]
            },
            "timeSig": {
                "isFolded": False,
                "events": [
                    {
                        "bar": 0,
                        "numer": time_sig[0],
                        "denom": time_sig[1]
                    }
                ]
            },
            "volume": {
                "isFolded": False,
                "height": 25.0,
                "events": [
                    {
                        "pos": 0,
                        "value": 0
                    }
                ]
            }
        },
        "voices": [
            {
                "compID": "BLRGDDR4M3WM2LC6",
                "name": "IA"
            }
        ],
        "tracks": [
            {
                "type": 0,
                "name": "1 VOCALOID",
                "color": 0,
                "busNo": 0,
                "isFolded": False,
                "height": 20.0,
                "volume": {
                    "isFolded": True,
                    "height": 20.0,
                    "events": [
                        {
                            "pos": 0,
                            "value": 0
                        }
                    ]
                },
                "panpot": {
                    "isFolded": True,
                    "height": 20.0,
                    "events": [
                        {
                            "pos": 0,
                            "value": 0
                        }
                    ]
                },
                "isMuted": False,
                "isSoloMode": False,
                "lastScrollPositionNoteNumber": 78,
                "parts": [
                    {
                        "pos": part_pos,
                        "duration": duration,
                        "styleName": "No Effect",
                        "voice": {
                            "compID": "BLRGDDR4M3WM2LC6",
                            "langID": 0
                        },
                        "midiEffects": [
                            {
                                "id": "SingingSkill",
                                "isBypassed": True,
                                "isFolded": False,
                                "parameters": [
                                    {
                                        "name": "Amount",
                                        "value": 5
                                    },
                                    {
                                        "name": "Name",
                                        "value": "75F04D2B-D8E4-44b8-939B-41CD101E08FD"
                                    },
                                    {
                                        "name": "Skill",
                                        "value": 5
                                    }
                                ]
                            },
                            {
                                "id": "VoiceColor",
                                "isBypassed": True,
                                "isFolded": False,
                                "parameters": [
                                    {
                                        "name": "Air",
                                        "value": 0
                                    },
                                    {
                                        "name": "Breathiness",
                                        "value": 0
                                    },
                                    {
                                        "name": "Character",
                                        "value": 27
                                    },
                                    {
                                        "name": "Exciter",
                                        "value": 0
                                    },
                                    {
                                        "name": "Growl",
                                        "value": 0
                                    },
                                    {
                                        "name": "Mouth",
                                        "value": 0
                                    },
                                    {
                                        "name": "VoiceBID",
                                        "value": ""
                                    },
                                    {
                                        "name": "VoiceBlend",
                                        "value": 0
                                    }
                                ]
                            },
                            {
                                "id": "RobotVoice",
                                "isBypassed": True,
                                "isFolded": False,
                                "parameters": [
                                    {
                                        "name": "Mode",
                                        "value": 1
                                    }
                                ]
                            },
                            {
                                "id": "DefaultLyric",
                                "isBypassed": True,
                                "isFolded": False,
                                "parameters": [
                                    {
                                        "name": "CHS",
                                        "value": "a"
                                    },
                                    {
                                        "name": "ENG",
                                        "value": "Ooh"
                                    },
                                    {
                                        "name": "ESP",
                                        "value": "a"
                                    },
                                    {
                                        "name": "JPN",
                                        "value": "あ"
                                    },
                                    {
                                        "name": "KOR",
                                        "value": "아"
                                    }
                                ]
                            },
                            {
                                "id": "Breath",
                                "isBypassed": True,
                                "isFolded": False,
                                "parameters": [
                                    {
                                        "name": "Exhalation",
                                        "value": 5
                                    },
                                    {
                                        "name": "Mode",
                                        "value": 1
                                    },
                                    {
                                        "name": "Type",
                                        "value": 0
                                    }
                                ]
                            }
                        ],
                        "notes": []
                    }
                ]
            }
        ]
    }
    
    # ノートデータを追加
    for note in notes:
        # singingSkillのdurationを音符の長さに応じて計算
        duration_ticks = note['duration']
        if duration_ticks >= 480:  # 4分音符以上
            singing_duration = 158
        elif duration_ticks >= 240:  # 8分音符以上
            singing_duration = 118
        else:  # 8分音符未満
            singing_duration = 79
        
        note_data = {
            "lyric": note['lyric'],
            "phoneme": note.get('phoneme', ''),
            "isProtected": False,
            # part.pos相対座標に変換
            "pos": note['pos'] - part_pos,
            "duration": note['duration'],
            "number": note['number'],
            "velocity": note.get('velocity', 64),
            "exp": {
                "opening": 127
            },
            "singingSkill": {
                "duration": singing_duration,
                "weight": {
                    "pre": 64,
                    "post": 64
                }
            },
            "vibrato": {
                "type": 0,
                "duration": 0
            }
        }
        vpr_data["tracks"][0]["parts"][0]["notes"].append(note_data)
    
    return vpr_data

def save_vpr_file(vpr_data, output_path):
    """VPRファイルとして保存"""
    # JSONを文字列に変換
    json_str = json.dumps(vpr_data, ensure_ascii=False, separators=(',', ':'))
    
    # ZIPファイルとして保存
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('Project/sequence.json', json_str.encode('utf-8'))

def main():
    """メイン関数 - ファイル内で直接パスを指定して変換"""
    # ここで変換したいファイルのパスを直接指定（常にlatest_data.mdを読む）
    text_file = "/Users/neromehiro/hiro folder/my_Works/programing/ROSVOT-test/output/001_1_VOCALOID__tyu-rti/d_analysis_report.json"
    
    # 変換設定
    output_file = "../dataset/restored/latest_data.vpr"
    title = "Converted Song"
    tempo = 136.0
    time_sig_str = "4/4"
    ticks_per_quarter = 480
    
    try:
        # テキストファイルを読み込み
        with open(text_file, 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        # メタデータを抽出
        metadata = parse_metadata(text_content)
        
        # メタデータがある場合は優先、なければ設定値を使用
        ticks_per_quarter = metadata.get('ticks_per_quarter', ticks_per_quarter)
        time_sig = metadata.get('time_sig', None)
        start_tick_offset = metadata.get('start_tick', 0)
        tempo = metadata.get('tempo', tempo)
        
        # 拍子記号をパース（メタデータがない場合）
        if time_sig is None:
            time_sig_parts = time_sig_str.split('/')
            time_sig = (int(time_sig_parts[0]), int(time_sig_parts[1]))
        
        print(f"メタデータ: start_tick={start_tick_offset}, ticks_per_quarter={ticks_per_quarter}, time_sig={time_sig}, tempo={tempo}")
        
        # テキストをパースして音符データを抽出
        notes = parse_text_table(text_content, time_sig, ticks_per_quarter, start_tick_offset, metadata.get('phonemes'))
        
        if not notes:
            print("エラー: 変換できる音符が見つかりません")
            return
        
        print(f"変換された音符数: {len(notes)}")
        
        # VPRデータを作成
        vpr_data = create_vpr_data(notes, title, tempo, time_sig, start_tick_offset)
        
        # VPRファイルとして保存
        save_vpr_file(vpr_data, output_file)
        
        print(f"変換完了: {output_file}")
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()


    """mdの例
    <!-- @start_tick=1920 @ticks_per_quarter=480 @time_sig=4/4 @tempo=120.0 @block_cycle=4 @block_anchors=0,7680,15360 @phonemes=sa@5760:s a|i@6240:i|ta@6720:t a|あ@7560:a|sa@7680:s a|i@8160:i|ta@8640:t a|chu@9600:tS M|ri@10080:4' i|ltu@10440:Sil|pu@10560:p M|no@11040:n o|ha@11520:h a|na@12000:n a|a@12240:a|ga@12480:g a|sa@13680:s a|i@13800:i|ta@13920:t a|yo@14040:j o|あ@14640:a|あ@14880:a -->
| 曲名 チューリップ | 1 | 2 |
| --- | --- | --- |
| **[0:00.0] 小節1** |  |  |
| A |  |  |
| B |  |  |
| C |  |  |
| D | [sa]1 C5,[i]1 D5 | [ta]1 E5,[ ]3/4,[あ]1/4 C5 |
| --- | --- | --- |
| **[0:08.0] 小節5** |  |  |
| A | [あ]-1/4 C5,[sa]1 C5,[i]1 D5 | [ta]1 E5 |
| B | [chu]1 G5,[ri]3/4 E5,[ ]0,[ltu]1/4 D#5 | [pu]1 D5,[no]1 C5 |
| C | [ha]1 D5,[na]1/2 D#5,[a]1/2 E5 | [ga]1 D5 |
| D | [ ]1/2,[sa]1/4 C5,[i]1/4 B4,[ta]1/4 C5,[yo]3/4 G5 | [-]1/2 G5,[あ]1/2 A5,[あ]1 G5 |
| --- | --- | --- |
| **[0:16.0] 小節9** |  |  |
| A | [-]1/2 G5 |  |
| B |  |  |
| C |  |  |
| D |  |  |
    
    
    """