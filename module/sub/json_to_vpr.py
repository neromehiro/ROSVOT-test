# module/sub/json_to_vpr.py

"""
d_analysis_report.jsonからVPRファイルを生成するツール
"""

import json
import zipfile
import os
import sys
from typing import List, Dict, Any

# 現在のディレクトリをパスに追加
sys.path.append(os.path.dirname(__file__))
from phoneme_mapping import get_phoneme

def seconds_to_ticks(seconds: float, tempo: float = 136.0, ticks_per_quarter: int = 480) -> int:
    """
    秒をtickに変換
    
    Args:
        seconds: 時刻（秒）
        tempo: テンポ（BPM）
        ticks_per_quarter: 四分音符あたりのtick数
        
    Returns:
        int: tick数
    """
    return int(seconds * (tempo / 60.0) * ticks_per_quarter)

def pitch_to_midi_number(pitch: int) -> int:
    """
    ピッチ番号をMIDI番号に変換（そのまま返す）
    
    Args:
        pitch: ピッチ番号
        
    Returns:
        int: MIDI番号
    """
    return pitch

def extract_notes_from_json(analysis_data: Dict[str, Any], tempo: float = 136.0) -> List[Dict[str, Any]]:
    """
    解析結果JSONから音符データを抽出
    
    Args:
        analysis_data: 解析結果データ
        tempo: テンポ（BPM）
        
    Returns:
        List[Dict]: 音符データのリスト
    """
    notes = []
    
    # word_coverageから音符を抽出
    word_coverage = analysis_data.get('detailed_results', {}).get('word_coverage', [])
    
    for word_data in word_coverage:
        if not word_data.get('has_midi', False):
            continue
            
        word = word_data.get('word', '')
        start_time = word_data.get('start', 0.0)
        end_time = word_data.get('end', 0.0)
        midi_notes = word_data.get('midi_notes', [])
        
        if not midi_notes:
            continue
            
        # 開始・終了時刻をtickに変換
        start_tick = seconds_to_ticks(start_time, tempo)
        end_tick = seconds_to_ticks(end_time, tempo)
        duration = end_tick - start_tick
        
        if duration <= 0:
            continue
            
        # 最初のMIDIノートを使用（複数ある場合）
        first_midi = midi_notes[0]
        pitch = first_midi.get('pitch', 60)
        
        # 音素を取得
        phoneme = get_phoneme(word)
        
        note = {
            'pos': start_tick,
            'duration': duration,
            'number': pitch,
            'lyric': word,
            'phoneme': phoneme,
            'velocity': 64
        }
        
        notes.append(note)
    
    # 位置でソート
    notes.sort(key=lambda x: x['pos'])
    
    # 重複する音符を結合
    merged_notes = merge_overlapping_notes(notes)
    
    return merged_notes

def merge_overlapping_notes(notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    重複する音符を結合
    
    Args:
        notes: 音符データのリスト
        
    Returns:
        List[Dict]: 結合後の音符データ
    """
    if not notes:
        return notes
    
    merged = []
    current_note = notes[0].copy()
    
    for i in range(1, len(notes)):
        next_note = notes[i]
        current_end = current_note['pos'] + current_note['duration']
        
        # 同じピッチで連続している場合は結合
        if (next_note['number'] == current_note['number'] and 
            abs(next_note['pos'] - current_end) <= 50):  # 50tick以内の隙間は許容
            
            # 長さを延長
            new_end = next_note['pos'] + next_note['duration']
            current_note['duration'] = new_end - current_note['pos']
            
            # 歌詞を結合（必要に応じて）
            if current_note['lyric'] != next_note['lyric']:
                current_note['lyric'] += next_note['lyric']
        else:
            # 異なるピッチまたは離れている場合は新しいノートとして追加
            merged.append(current_note)
            current_note = next_note.copy()
    
    # 最後のノートを追加
    merged.append(current_note)
    
    return merged

def create_vpr_data(notes: List[Dict[str, Any]], title: str = "Restored Song", 
                   tempo: float = 136.0, time_sig: tuple = (4, 4)) -> Dict[str, Any]:
    """
    音符データからVPRのJSONデータを作成
    
    Args:
        notes: 音符データのリスト
        title: 曲名
        tempo: テンポ
        time_sig: 拍子記号
        
    Returns:
        Dict: VPRデータ
    """
    
    # 最後のノートの終了位置を計算
    if notes:
        max_end_pos = max(note['pos'] + note['duration'] for note in notes)
        duration = max_end_pos
    else:
        duration = 7680
    
    # 基本構造を作成
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
                        "pos": 0,
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
            "pos": note['pos'],
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

def save_vpr_file(vpr_data: Dict[str, Any], output_path: str):
    """
    VPRファイルとして保存
    
    Args:
        vpr_data: VPRデータ
        output_path: 出力ファイルパス
    """
    # JSONを文字列に変換
    json_str = json.dumps(vpr_data, ensure_ascii=False, separators=(',', ':'))
    
    # 出力ディレクトリを作成
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # ZIPファイルとして保存
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('Project/sequence.json', json_str.encode('utf-8'))

def main():
    """メイン関数"""
    # 入力ファイルパス
    input_file = "/Users/neromehiro/hiro folder/my_Works/programing/ROSVOT-test/output/001_1_VOCALOID__tyu-rti/d_analysis_report.json"
    
    # 出力ファイルパス（入力ファイルと同じディレクトリに出力）
    input_dir = os.path.dirname(input_file)
    output_file = os.path.join(input_dir, "restored_song.vpr")
    
    # 設定
    title = "Restored Tulip Song"
    tempo = 136.0
    time_sig = (4, 4)
    
    try:
        # JSONファイルを読み込み
        with open(input_file, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
        
        print(f"解析データを読み込みました: {input_file}")
        
        # 音符データを抽出
        notes = extract_notes_from_json(analysis_data, tempo)
        
        if not notes:
            print("エラー: 変換できる音符が見つかりません")
            return
        
        print(f"抽出された音符数: {len(notes)}")
        
        # 音符情報を表示
        print("\n音符情報:")
        for i, note in enumerate(notes[:10]):  # 最初の10個だけ表示
            start_sec = note['pos'] / (tempo / 60.0 * 480)
            print(f"  {i+1}: '{note['lyric']}' ({note['phoneme']}) - "
                  f"pos={note['pos']} ({start_sec:.2f}s), "
                  f"dur={note['duration']}, pitch={note['number']}")
        
        if len(notes) > 10:
            print(f"  ... (他 {len(notes) - 10} 個)")
        
        # VPRデータを作成
        vpr_data = create_vpr_data(notes, title, tempo, time_sig)
        
        # VPRファイルとして保存
        save_vpr_file(vpr_data, output_file)
        
        print(f"\nVPRファイルを作成しました: {output_file}")
        print(f"曲名: {title}")
        print(f"テンポ: {tempo} BPM")
        print(f"拍子: {time_sig[0]}/{time_sig[1]}")
        
    except FileNotFoundError:
        print(f"エラー: 入力ファイルが見つかりません: {input_file}")
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
