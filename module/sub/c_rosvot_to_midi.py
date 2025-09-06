# module/sub/c_rosvot_to_midi.py
########## [Script Entry Point] パス設定ブロック - 開始 ##########
import sys
import os

def _getenv_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

if __name__ == "__main__" and __package__ is None:
    # スクリプトが直接実行された場合、プロジェクトのルートディレクトリをsys.pathに追加
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "../../")) # 2階層下の場合
    sys.path.insert(0, project_root)
########## [Script Entry Point] パス設定ブロック - 終了 ##########

import json
import subprocess
import shutil
import tempfile
import numpy as np
from pathlib import Path
from typing import Dict, Optional

class ROSVOTRunner:
    """ROSVOTを実行するクラス"""
    
    def __init__(self, rosvot_dir: str = "ROSVOT"):
        self.rosvot_dir = Path(rosvot_dir)
    
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
                "-v",
                "--thr", os.getenv("ROSVOT_THR", "0.35")  # 極端設定: 閾値をさらに下げる
            ]
            
            # TODO: ROSVOTの内部パラメータ調整は後で実装
            # 現在は後処理での補完強化で対応
            
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

def repair_micro_gaps_with_phonemes(
    midi_path: str,
    timestamps_path: str,
    *,
    min_phoneme_dur: float = 0.025,  # 25ms 未満はノイズ扱いで無視（短子音対応）
    max_fill_dur: float = 0.25,      # 250ms までを"短い欠落"として埋める
    min_overlap_for_covered: float = 0.01,  # 10ms 重なれば"カバー済み"とみなす
    max_neighbor_gap: float = 0.14,  # 前後ノートからの距離がこれ以下なら借用OK（拡大）
    insert_velocity: int = 64
) -> bool:
    """
    phonesに有声があるのにMIDIが無い"短い区間"だけ、近傍ノートのピッチで小ノートを挿入する。
    - 末尾延長や長大区間の復元はしない（無音は尊重）。
    """
    try:
        import json
        import pretty_midi

        # timestamps 読み込み
        with open(timestamps_path, "r", encoding="utf-8") as f:
            ts = json.load(f)

        phones = [(s, e, p) for (s, e, p) in ts["phonemes"] if p not in ("SP", "AP", "")]
        # 短すぎる有声 phones は除外
        phones = [(s, e, p) for (s, e, p) in phones if (e - s) >= min_phoneme_dur]
        if not phones:
            print("[MICROFIX] 有効な有声phonesがありません。スキップ")
            return False

        midi = pretty_midi.PrettyMIDI(midi_path)
        if not midi.instruments:
            print("[MICROFIX] MIDI楽器が空です。スキップ")
            return False
        inst = midi.instruments[0]
        notes = sorted(inst.notes, key=lambda n: (n.start, n.end))

        def overlap(a0, a1, b0, b1):
            return max(0.0, min(a1, b1) - max(a0, b0))

        def find_prev_next(t):
            prev = None
            nxt = None
            # 二分探索でもよいが件数少なので線形でOK
            for n in notes:
                if n.end <= t:
                    prev = n
                elif n.start >= t:
                    nxt = n
                    break
            return prev, nxt

        inserted = 0
        for (s, e, p) in phones:
            if (e - s) > max_fill_dur:
                # 長い区間は対象外（無音やロング息継ぎは尊重）
                continue

            # この phones 区間が既存ノートでどれだけカバーされているか調べる
            cov = 0.0
            for n in notes:
                if n.start >= e:
                    break
                if n.end <= s:
                    continue
                cov += overlap(s, e, n.start, n.end)
            if cov >= min_overlap_for_covered:
                # 既にある程度カバーされているならスキップ
                continue

            # 近傍ノートからピッチ候補
            prev, nxt = find_prev_next((s + e) * 0.5)
            candidates = []
            if prev:
                gap = max(0.0, s - prev.end)
                candidates.append(("prev", gap, prev.pitch))
            if nxt:
                gap = max(0.0, nxt.start - e)
                candidates.append(("next", gap, nxt.pitch))

            if not candidates:
                continue

            # 最も近い候補を採用
            src, gap, pitch = min(candidates, key=lambda x: x[1])
            if gap > max_neighbor_gap:
                # 近傍とみなせない距離なら挿入しない（誤爆防止）
                continue

            # phones 区間に小ノートを挿入（前後ノートに食い込み過ぎないよう軽くクリップ）
            start_t = s
            end_t = e
            if prev:
                start_t = max(start_t, prev.end)
            if nxt:
                end_t = min(end_t, nxt.start)
            if end_t - start_t < min_phoneme_dur:
                continue

            note = pretty_midi.Note(
                velocity=insert_velocity,
                pitch=int(pitch),
                start=float(start_t),
                end=float(end_t),
            )
            inst.notes.append(note)
            inserted += 1

        if inserted > 0:
            # 追加後に時間順ソート＆同一ピッチで短ギャップならマージ
            inst.notes.sort(key=lambda n: (n.start, n.end))
            merged = [inst.notes[0]]
            for n in inst.notes[1:]:
                m = merged[-1]
                if n.pitch == m.pitch and (n.start - m.end) <= 0.02:
                    m.end = max(m.end, n.end)
                else:
                    merged.append(n)
            inst.notes = merged

            midi.write(midi_path)
            print(f"[MICROFIX] 追加ノート数: {inserted} （短欠落の復元）")
            return True
        else:
            print("[MICROFIX] 追加不要（対象なし）")
            return False

    except Exception as e:
        print(f"[MICROFIX] エラー: {e}")
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
    
    def _infer_time_per_frame(self, pitch, rosvot_metadata, default_tpf):
        """WAV長とフレーム数から時間/フレームを推定"""
        try:
            if rosvot_metadata and "wav_fn" in rosvot_metadata:
                import librosa
                dur = librosa.get_duration(filename=rosvot_metadata["wav_fn"])
                tpf_est = dur / max(1, len(pitch))
                # 15ms〜30ms の合理範囲にあれば採用（RMVPEは約20ms）
                if 0.015 <= tpf_est <= 0.030:
                    return tpf_est
            return default_tpf
        except Exception:
            return default_tpf
    
    def _bridge_unvoiced_gaps(self, f0, max_gap_frames):
        """短い無声区間をブリッジしてノートを途切れさせない"""
        f0 = f0.copy()
        voiced = (f0 > 0).astype(np.int8)
        run = 0
        start = -1
        
        for i, x in enumerate(voiced):
            if x == 0:
                if run == 0:
                    start = i
                run += 1
            else:
                if 0 < run <= max_gap_frames:
                    # 前後の値で埋める
                    left = f0[start-1] if start-1 >= 0 and f0[start-1] > 0 else 0
                    right = f0[i] if i < len(f0) and f0[i] > 0 else 0
                    fill = left if right == 0 else (right if left == 0 else (left + right) / 2)
                    f0[start:i] = max(fill, 1e-6)
                run = 0
        return f0
    
    def _merge_short_splits(self, notes, gap_thresh=None):
        if gap_thresh is None:
            gap_thresh = _getenv_float("MERGE_GAP_S", 0.06)
        """短い休符で分断された同じピッチのノートをマージ"""
        if not notes:
            return notes
        
        merged = [notes[0]]
        for n in notes[1:]:
            prev = merged[-1]
            if n.pitch == prev.pitch and (n.start - prev.end) <= gap_thresh:
                prev.end = n.end
            else:
                merged.append(n)
        return merged
    
    def create_midi_from_pitch(self, pitch_data: np.ndarray, onset_data: Optional[np.ndarray], 
                              output_path: str, min_note_duration: float = None, rosvot_metadata: Optional[Dict] = None) -> bool:
        # 環境変数で最小ノート長を上書き可能
        if min_note_duration is None:
            min_note_duration = _getenv_float("MIN_NOTE_S", 0.01)
        force_split_phonemes = os.getenv("FORCE_SPLIT_PHONEMES", "").split(",") if os.getenv("FORCE_SPLIT_PHONEMES") else []
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
            
            # 時間軸を計算（自動推定機能付き）
            default_tpf = self.hop_length / self.sample_rate
            time_per_frame = self._infer_time_per_frame(pitch_data, rosvot_metadata, default_tpf)
            print(f"[DEBUG] time_per_frame={time_per_frame:.5f}s")
            
            # WAV長とフレーム数からFPSを推計
            if rosvot_metadata and "wav_fn" in rosvot_metadata:
                try:
                    import librosa
                    wav_dur = librosa.get_duration(filename=rosvot_metadata["wav_fn"])
                    N = len(pitch_data)
                    est_fps = N / wav_dur
                    print(f"[DEBUG] wav_dur={wav_dur:.3f}s, frames={N}, est_fps={est_fps:.2f}fps")
                except Exception:
                    pass
            
            # --- DEBUG: voiced coverage around 13-16s ---
            def _voiced_coverage(pitch, tpf, a, b):
                i0, i1 = int(a/tpf), int(b/tpf)
                seg = pitch[max(0,i0):min(len(pitch),i1)]
                if len(seg)==0: return 0.0, 0, 0
                voiced = np.sum(seg > 0)
                return voiced/len(seg), voiced, len(seg)
            
            cov, v, L = _voiced_coverage(pitch_data, time_per_frame, 13.0, 16.3)
            print(f"[DEBUG] voiced coverage 13-16.3s: {cov*100:.1f}% ({v}/{L} frames)")
            
            # 最終有声フレームの確認
            last_voiced_idx = np.max(np.where(pitch_data>0)[0]) if np.any(pitch_data>0) else -1
            last_voiced_sec = (last_voiced_idx+1) * time_per_frame if last_voiced_idx >= 0 else 0
            print(f"[DEBUG] last_voiced_sec≈{last_voiced_sec:.3f}s")
            
            # 短い無声区間をブリッジ
            bridge_ms = _getenv_float("BRIDGE_GAP_MS", 0.0)
            pitch_data = self._bridge_unvoiced_gaps(pitch_data, max_gap_frames=int((bridge_ms/1000.0)/time_per_frame))
            
            # ピッチデータを処理
            current_note = None
            current_start_time = 0
            
            for i, pitch_hz in enumerate(pitch_data):
                current_time = i * time_per_frame

                if pitch_hz > 0:  # 有効なピッチ
                    midi_note = self.hz_to_midi_note(pitch_hz)

                    # 音素境界で強制分割（有声連続中でも）
                    force_cut = False
                    if force_split_phonemes and rosvot_metadata and "phonemes" in rosvot_metadata:
                        for (ps, pe, ph) in rosvot_metadata["phonemes"]:
                            # 現在時刻が音素境界の±1フレーム以内かつ対象音素なら切る
                            if abs(ps - current_time) <= time_per_frame and ph in force_split_phonemes:
                                force_cut = True
                                break

                    if current_note is None:
                        # 新しいノートの開始
                        current_note = midi_note
                        current_start_time = current_time
                    elif abs(midi_note - current_note) > 0.5 or force_cut:  # ピッチ変化 or 強制カット
                        # 前のノートを終了
                        if current_time - current_start_time >= min_note_duration or force_cut:
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
                        # 強制分割対象の音素が直後に来る場合は短くても切る
                        force_cut = False
                        if force_split_phonemes and rosvot_metadata and "phonemes" in rosvot_metadata:
                            # 現在時刻に最も近い音素を探す
                            for (ps, pe, ph) in rosvot_metadata["phonemes"]:
                                if ps >= current_time and ph in force_split_phonemes:
                                    force_cut = True
                                    break
                        if (current_time - current_start_time >= min_note_duration) or force_cut:
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
            
            # 短い休符で分断された同じピッチのノートをマージ
            instrument.notes = self._merge_short_splits(instrument.notes, gap_thresh=-1.0)  # マージ完全無効化
            
            # MIDIファイルに楽器を追加
            midi.instruments.append(instrument)
            
            # MIDIファイルを保存
            midi.write(output_path)
            print(f"MIDIファイルを保存しました: {output_path}")
            
            # MIDI終端時刻を表示
            midi_end_time = midi.get_end_time()
            print(f"[DEBUG] MIDI終端時刻: {midi_end_time:.3f}s")
            
            return True
            
        except Exception as e:
            print(f"MIDI作成エラー: {e}")
            return False
    
    def midi_from_note_arrays(self, note_dict, bd_data, output_path, rosvot_metadata, min_note=0.05, gap_merge=0.06):
        """NPYファイルからMIDIを生成（境界データを活用）"""
        try:
            import pretty_midi
            import librosa
            
            midi = pretty_midi.PrettyMIDI()
            instrument = pretty_midi.Instrument(program=0)
            
            # ROSVOTの時間解像度
            TPF = 128 / 24000.0
            
            # ノートデータから有効なピッチノートを抽出
            pitches = note_dict['pitches']
            note_durs = note_dict['note_durs']
            
            print(f"[DEBUG] NPY→MIDI変換開始")
            print(f"[DEBUG] ノート数: {len(pitches)}")
            
            # 累積時間でノートを生成
            cumulative_time = 0
            for i, (pitch, dur) in enumerate(zip(pitches, note_durs)):
                start_time = cumulative_time
                end_time = cumulative_time + dur
                
                # pitch > 0 の場合のみMIDIノートとして追加
                if pitch > 0 and dur >= min_note:
                    note = pretty_midi.Note(
                        velocity=80,
                        pitch=int(pitch),
                        start=start_time,
                        end=end_time
                    )
                    instrument.notes.append(note)
                    print(f"[DEBUG] ノート追加: {start_time:.3f}s-{end_time:.3f}s pitch={pitch}")
                
                cumulative_time = end_time
            
            # 境界データから追加のノートを推定（14.48秒以降）
            wav_dur = librosa.get_duration(filename=rosvot_metadata["wav_fn"])
            if cumulative_time < wav_dur - 1.0:
                print(f"[DEBUG] 境界データから追加ノートを推定中...")
                
                # 14.48秒以降の境界データを確認
                t_cut = 14.48
                i_cut = int(t_cut / TPF)
                
                if i_cut < len(bd_data):
                    tail_bd = bd_data[i_cut:]
                    # 境界スコアが高い部分を音として扱う
                    high_bd_indices = np.where(tail_bd > 0.3)[0]  # 閾値を下げて検出
                    
                    if len(high_bd_indices) > 0:
                        # 最後の有効ピッチを使用して延長
                        last_valid_pitch = 74  # 最後のノート26のピッチ
                        
                        # 境界データから連続区間を抽出
                        segments = []
                        start_idx = None
                        
                        for idx in high_bd_indices:
                            if start_idx is None:
                                start_idx = idx
                            elif idx > high_bd_indices[segments[-1] if segments else 0] + 10:  # ギャップがある場合
                                if start_idx is not None:
                                    segments.append((start_idx, high_bd_indices[np.where(high_bd_indices < idx)[0][-1]]))
                                start_idx = idx
                        
                        # 最後のセグメントを追加
                        if start_idx is not None:
                            segments.append((start_idx, high_bd_indices[-1]))
                        
                        # セグメントをノートに変換
                        for seg_start, seg_end in segments:
                            note_start = t_cut + seg_start * TPF
                            note_end = t_cut + (seg_end + 1) * TPF
                            note_dur = note_end - note_start
                            
                            if note_dur >= min_note:
                                note = pretty_midi.Note(
                                    velocity=60,  # 推定ノートは少し弱く
                                    pitch=last_valid_pitch,
                                    start=note_start,
                                    end=note_end
                                )
                                instrument.notes.append(note)
                                print(f"[DEBUG] 境界から推定ノート: {note_start:.3f}s-{note_end:.3f}s pitch={last_valid_pitch}")
            
            # 短い休符で分断された同じピッチのノートをマージ
            merged = []
            for note in sorted(instrument.notes, key=lambda n: n.start):
                if merged and note.pitch == merged[-1].pitch and (note.start - merged[-1].end) <= gap_merge:
                    merged[-1].end = note.end
                else:
                    merged.append(note)
            
            instrument.notes = merged
            midi.instruments.append(instrument)
            
            # MIDIファイルを保存
            midi.write(output_path)
            print(f"[DEBUG] NPY→MIDI変換完了: {midi.get_end_time():.3f}秒")
            
            return True
            
        except Exception as e:
            print(f"NPY→MIDI変換エラー: {e}")
            return False

def rosvot_to_midi(rosvot_metadata: Dict, output_dir: Path) -> Optional[str]:
    """
    ROSVOT形式のメタデータからMIDIファイルを生成
    
    Args:
        rosvot_metadata: ROSVOT形式のメタデータ
        output_dir: 出力ディレクトリ
        
    Returns:
        midi_path: 生成されたMIDIファイルのパス（失敗時はNone）
    """
    try:
        item_name = rosvot_metadata["item_name"]
        
        # デバッグ用に永続ディレクトリを使用
        temp_dir = output_dir / "__rosvot_debug__"
        temp_dir.mkdir(exist_ok=True)
        
        # メタデータファイルを一時保存
        temp_metadata_path = Path(temp_dir) / "metadata.json"
        with open(temp_metadata_path, 'w', encoding='utf-8') as f:
            json.dump([rosvot_metadata], f, indent=2, ensure_ascii=False)
        
        # ROSVOT実行
        rosvot_runner = ROSVOTRunner()
        rosvot_output_dir = Path(temp_dir) / "rosvot_output"
        
        success = rosvot_runner.run_rosvot(str(temp_metadata_path), str(rosvot_output_dir))
        
        if not success:
            print("ROSVOT実行に失敗しました")
            return None
        
        # ROSVOTの出力ディレクトリの内容を確認
        print(f"[DEBUG] ROSVOTの出力ディレクトリ: {rosvot_output_dir}")
        if rosvot_output_dir.exists():
            all_files = list(rosvot_output_dir.rglob("*"))
            print(f"[DEBUG] 生成されたファイル数: {len(all_files)}")
            for f in all_files[:10]:  # 最初の10個を表示
                print(f"  - {f}")
        
        # ROSVOTが生成したMIDIファイルを確認
        rosvot_midi_path = rosvot_output_dir / "midi" / f"{item_name}.mid"
        
        use_rosvot_midi = int(os.getenv("USE_ROSVOT_MIDI", "1"))
        if rosvot_midi_path.exists() and use_rosvot_midi == 1:
            final_midi_path = output_dir / "c_output.mid"
            shutil.copy2(str(rosvot_midi_path), str(final_midi_path))
            print(f"ROSVOTが生成したMIDIファイルを使用: {rosvot_midi_path}")
            print(f"最終MIDIファイル: {final_midi_path}")
        else:
            print("ROSVOTのMIDIを使用せず、フォールバック変換を実行します。")
            midi_converter = MIDIConverter()
            rosvot_results = midi_converter.load_rosvot_results(str(rosvot_output_dir), item_name)
            if not rosvot_results:
                print("ROSVOTの結果を読み込めませんでした")
                return None
            final_midi_path = output_dir / "c_output.mid"
            os.environ["FORCE_SPLIT_TS_PATH"] = str(output_dir / "a_timestamps.json")
            success = midi_converter.create_midi_from_pitch(
                rosvot_results['pitch'],
                rosvot_results.get('onset'),
                str(final_midi_path),
                min_note_duration=0.015,
                rosvot_metadata=rosvot_metadata
            )
            if not success:
                print("MIDI変換に失敗しました")
                return None
        
        # 後段強制分割
        timestamps_path = output_dir / "a_timestamps.json"
        force_mode = os.getenv("FORCE_SPLIT", "none")
        if force_mode in ("words", "phonemes") and timestamps_path.exists():
            print(f"[POST] FORCE_SPLIT={force_mode} を適用")
            force_split_midi_by_boundaries(str(final_midi_path), str(timestamps_path), mode=force_mode)
        
        return str(final_midi_path)
                    
    except Exception as e:
        print(f"ROSVOT→MIDI変換エラー: {e}")
        return None

def find_latest_rosvot_metadata_file() -> Optional[str]:
    """最新のb_rosvot_metadata.jsonファイルを探す"""
    output_dir = Path("output")
    if not output_dir.exists():
        return None
    
    # 全てのb_rosvot_metadata.jsonファイルを探す
    metadata_files = list(output_dir.glob("*/b_rosvot_metadata.json"))
    
    if not metadata_files:
        return None
    
    # 最新のファイルを返す（更新時刻順）
    latest_file = max(metadata_files, key=lambda f: f.stat().st_mtime)
    return str(latest_file)

def _main_impl():
    """メイン処理"""
    print("=== ROSVOTを実行してMIDIファイルを生成 ===")
    
    # 前のモジュールの成果物を自動で探す
    metadata_file = find_latest_rosvot_metadata_file()
    
    if not metadata_file:
        print("❌ b_rosvot_metadata.jsonファイルが見つかりません")
        print("🔗 先に以下を実行してください: python module/sub/b_convert_to_rosvot.py")
        return None
    
    print(f"📁 入力ファイル: {metadata_file}")
    
    # ROSVOTメタデータファイルを読み込み
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata_array = json.load(f)
        rosvot_metadata = metadata_array[0]  # 配列の最初の要素
    except Exception as e:
        print(f"❌ ROSVOTメタデータファイル読み込みエラー: {e}")
        return None
    
    print(f"📊 アイテム名: {rosvot_metadata['item_name']}")
    print(f"🎵 WAVファイル: {rosvot_metadata['wav_fn']}")
    print(f"📈 単語持続時間数: {len(rosvot_metadata['word_durs'])}")
    
    # 出力ディレクトリを取得
    output_dir = Path(metadata_file).parent
    
    # ROSVOT→MIDI変換を実行
    midi_path = rosvot_to_midi(rosvot_metadata, output_dir)
    
    if midi_path:
        print("\n✅ ROSVOT→MIDI変換成功!")
        print(f"📁 成果物を保存: {midi_path}")
        
        # ファイルサイズを確認
        if Path(midi_path).exists():
            file_size = Path(midi_path).stat().st_size
            print(f"📊 MIDIファイルサイズ: {file_size} bytes")
            
            # 短い欠落区間の修復を実行
            try:
                timestamps_path = output_dir / "a_timestamps.json"
                if timestamps_path.exists():
                    if os.getenv("SKIP_MICROFIX", "0") != "1":
                        print("\n🔧 短い欠落区間の修復を実行中...")
                        repair_micro_gaps_with_phonemes(midi_path, str(timestamps_path))
                    else:
                        print("[MICROFIX] one-phoneme-one-noteモードなのでスキップ")
                else:
                    print(f"[MICROFIX] {timestamps_path} が無いのでスキップ")
            except Exception as e:
                print(f"[MICROFIX] 呼び出し時エラー: {e}")
            
            print(f"🎉 パイプライン完了! 最終成果物: {midi_path}")
            
            return midi_path
        else:
            print("❌ MIDIファイルが見つかりません")
            return None
    else:
        print("\n❌ ROSVOT→MIDI変換失敗")
        return None


def main(min_note_s=0.01, rosvot_thr=0.35, merge_gap_s=0.06, bridge_gap_ms=0.0):
    """パラメータを環境変数にセットしてメイン処理を実行"""
    os.environ["MIN_NOTE_S"] = str(min_note_s)
    os.environ["ROSVOT_THR"] = str(rosvot_thr)
    os.environ["MERGE_GAP_S"] = str(merge_gap_s)
    os.environ["BRIDGE_GAP_MS"] = str(bridge_gap_ms)
    return _main_impl()


# ===== 追加: MIDI解析 + VPR生成 + 音符情報簡易表示 =====
from module.sub.d_analyze_midi_results import MIDIAnalyzer
from module.sub.json_to_vpr import extract_notes_from_json, create_vpr_data, save_vpr_file
import pretty_midi
import json

if __name__ == "__main__":
    # ここで値を直接変更可能
    # min_note_s: 最小ノート長（秒） - この長さ未満のノートは無視（短すぎる音符を除外）
    # rosvot_thr: ピッチ検出の信頼度閾値 - 小さいほど感度が高くなり、弱い音も検出されやすい
    # merge_gap_s: 同一ピッチのノートをマージする際の最大休符長（秒） - この間隔以下なら1つのノートに結合
    # bridge_gap_ms: 無声区間をブリッジする最大長（ミリ秒） - 短い無声区間を前後の有声で埋めてノートを途切れさせない
    main(
        min_note_s=0.015,
        rosvot_thr=0.1,
        merge_gap_s=0.05,
        bridge_gap_ms=0.1
    )

    # 最新出力ディレクトリを取得
    from pathlib import Path
    output_dir = Path("output")
    if output_dir.exists():
        latest_dir = max([d for d in output_dir.iterdir() if d.is_dir()], key=lambda d: d.stat().st_mtime)
        timestamps_path = latest_dir / "a_timestamps.json"
        midi_path = latest_dir / "c_output.mid"
        analysis_json_path = latest_dir / "d_analysis_report.json"
        vpr_path = latest_dir / "restored_song.vpr"

        if timestamps_path.exists() and midi_path.exists():
            print("\n=== 自動解析を実行中 ===")
            analyzer = MIDIAnalyzer()
            if analyzer.load_timestamps(str(timestamps_path)) and analyzer.load_midi(str(midi_path)):
                analyzer.analyze_coverage()
                analyzer.generate_report(str(analysis_json_path))

                # VPR生成
                with open(analysis_json_path, "r", encoding="utf-8") as f:
                    analysis_data = json.load(f)
                notes = extract_notes_from_json(analysis_data, tempo=136.0)
                vpr_data = create_vpr_data(notes, title="Restored Song", tempo=136.0, time_sig=(4,4))
                save_vpr_file(vpr_data, str(vpr_path))
                print(f"✅ VPRファイル生成完了: {vpr_path}")

                # 音符情報簡易表示（全音符）
                print("\n🎵 音符情報:")
                for i, note in enumerate(notes, 1):
                    start_sec = note['pos'] / (136.0 / 60.0 * 480)
                    note_name = pretty_midi.note_number_to_name(note['number'])
                    print(f"  {i}: '{note['lyric']}' ({note.get('phoneme','')})  ({start_sec:.2f}s), {note_name}")
        else:
            print("❌ タイムスタンプまたはMIDIファイルが見つかりません。")
