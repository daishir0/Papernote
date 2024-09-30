"""
このプログラムは、指定されたYouTubeのURLから動画をダウンロードし、動画から指定された間隔でフレームを抽出し、
字幕をダウンロードしてテキストファイルとして保存し、最終的にはすべての成果物をテキストファイルにまとめて出力します。

## 処理の仕様:
1. コマンドライン引数からYouTubeのURLとフレーム抽出の間隔（秒）を受け取ります。
2. 指定されたURLから動画をダウンロードします。
3. ダウンロードした動画から指定された間隔でフレームを抽出し、画像ファイルとして保存します。
4. YouTubeのAPIを使用して動画の字幕をダウンロードし、テキストファイルとして保存します。
5. 抽出したフレームとダウンロードした字幕を含むテキストファイルを生成し、指定のディレクトリに保存します。
6. 必要に応じて、動画ファイルをMP3に変換し、特定のタイムスタンプで音声ファイルを分割し、それらをテキストに変換します。

## コマンド例:
- YouTubeのURLとフレーム抽出間隔を指定して実行する例:
  ```
  python create_youtubemd.py https://www.youtube.com/watch?v=example 10
  ```
- デフォルトのフレーム抽出間隔（10秒）を使用して実行する例:
  ```
  python create_youtubemd.py https://www.youtube.com/watch?v=example
  ```
- ローカルの動画ファイルからフレームを抽出し、MP3に変換して音声をテキストに変換する例:
  ```
  python create_youtubemd.py local_movie.mp4 5
  ```
"""

import sys
import os
import uuid
import hashlib
from datetime import datetime, timedelta
import subprocess
import cv2
import numpy as np
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
from PIL import Image, ExifTags
from openai import OpenAI
import time
import yt_dlp
import yaml

def download_video(url):
    # 動画をダウンロードする関数
    try:
        yt = YouTube(url)
        title = yt.title  # 動画のタイトルを取得
        stream = yt.streams.filter(file_extension='mp4').get_highest_resolution()
        filename = f"{uuid.uuid4()}.mp4"
        stream.download(filename=filename)
        print("Downloaded with pytube")
        return filename, title  # タイトルも返すように変更
    except Exception as e:
        print(f"pytube failed: {e}")
        print("Trying to download with yt-dlp...")
        return download_video_with_ytdlp(url)

def download_video_with_ytdlp(url):
    # yt-dlpを使用して動画をダウンロードする関数
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': '%(id)s.%(ext)s',
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
            title = info_dict.get('title', None)
            print("Downloaded with yt-dlp")
            return filename, title
    except Exception as e:
        print(f"yt-dlp failed: {e}")
        sys.exit(1)

def extract_frames(video_path, interval_sec, output_dir="./tmp", threshold=0.1, sample_size=(10, 10)):
    # 動画からフレームを抽出する関数
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("動画ファイルを開けませんでした。")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    current_time = 0
    success, prev_frame = cap.read()
    if success:
        prev_frame_small = cv2.resize(prev_frame, sample_size)
        timestamp = (datetime.utcfromtimestamp(current_time)).strftime("%H%M%S-%f")[:-3]
        cv2.imwrite(f"{output_dir}/{timestamp}.png", prev_frame)
    else:
        print("最初のフレームを読み込めませんでした。")
        return

    while current_time <= duration:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * current_time))
        success, frame = cap.read()
        if success:
            frame_small = cv2.resize(frame, sample_size)
            diff = np.sum(frame_small != prev_frame_small) / (sample_size[0] * sample_size[1] * 3)
            if diff >= threshold:
                timestamp = (datetime.utcfromtimestamp(current_time)).strftime("%H%M%S-%f")[:-3]
                cv2.imwrite(f"{output_dir}/{timestamp}.png", frame)
                prev_frame_small = frame_small
        current_time += interval_sec

    cap.release()
    print("フレーム抽出完了")

def download_subtitles(video_id, output_dir="./tmp"):
    # 字幕をダウンロードする関数
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    transcript = transcript_list.find_transcript(['ja', 'en'])
    subtitles = transcript.fetch()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for subtitle in subtitles:
        start_time = subtitle['start']
        timestamp = datetime.utcfromtimestamp(start_time).strftime("%H%M%S-%f")[:-3]
        file_path = os.path.join(output_dir, f"{timestamp}.txt")

        with open(file_path, 'w', encoding='utf-8') as current_file:
            current_file.write(f"{subtitle['text']}\n")
    print("字幕ダウンロード完了")

def calculate_sha256(file_path):
    # ファイルのSHA256ハッシュを計算する関数
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def process_output_files(output_dir, result_filename, youtube_url, video_title):
    # 出力ファイルを処理する関数
    # files = sorted(os.listdir(output_dir), key=lambda x: (os.path.splitext(x)[0], os.path.splitext(x)[1]), reverse=True)
    files = sorted(os.listdir(output_dir), key=lambda x: (os.path.splitext(x)[0], -ord(os.path.splitext(x)[1][1])), reverse=False)
    with open(result_filename, 'w', encoding='utf-8') as result_file:
        result_file.write(f"##{video_title}\n\n")  # タイトルを追加
        result_file.write(f"{youtube_url}\n\n")
        previous_text = ""
        for file in files:
            file_path = os.path.join(output_dir, file)
            if file.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    # text = f.read().strip()
                    text = f.read()
                    if previous_text:
                        previous_text += " " + text
                    else:
                        previous_text = text
            elif file.endswith('.png'):
                if previous_text:
                    result_file.write(previous_text + "\n")
                    previous_text = ""
                file_hash = calculate_sha256(file_path)
                new_filename = f"{file_hash}.png"
                new_file_path = os.path.join('./attach', new_filename)
                os.rename(file_path, new_file_path)
                
                image = Image.open(new_file_path)
                try:
                    for orientation in ExifTags.TAGS.keys():
                        if ExifTags.TAGS[orientation] == 'Orientation':
                            break
                    exif = image._getexif()
                    if exif is not None:
                        orientation = exif.get(orientation, None)
                        if orientation == 3:
                            image = image.rotate(180, expand=True)
                        elif orientation == 6:
                            image = image.rotate(270, expand=True)
                        elif orientation == 8:
                            image = image.rotate(90, expand=True)
                except (AttributeError, KeyError, IndexError):
                    pass

                small_image = image.copy()
                small_image.thumbnail((400, 400), Image.Resampling.LANCZOS)
                small_filename = f"s_{new_filename}"
                small_file_path = os.path.join('./attach', small_filename)
                small_image.save(small_file_path)

                result_file.write("\n")
                result_file.write(f"[![image.png](/attach/{small_filename})](/attach/{new_filename})\n\n")
        if previous_text:
            result_file.write(previous_text + "\n")
    print("出力ファイル処理完了")

def convert_to_mp3(video_path):
    # 動画をmp3に変換する関数
    mp3_filename = f"{os.path.splitext(video_path)[0]}.mp3"
    command = f"ffmpeg -y -i {video_path} -q:a 0 -map a {mp3_filename}"
    subprocess.run(command, shell=True)
    return mp3_filename

def split_audio(mp3_path, timestamps, output_dir="./tmp"):
    # 音声ファイルを分割する関数
    for i in range(1, len(timestamps)):
        start_time = timestamps[i - 1]
        end_time = timestamps[i]
        # HHMMSS 式を HH:MM:SS 形式に変換
        start_time_formatted = f"{start_time[:2]}:{start_time[2:4]}:{start_time[4:]}"
        end_time_formatted = f"{end_time[:2]}:{end_time[2:4]}:{end_time[4:]}"
        output_file = os.path.join(output_dir, f"{end_time}.mp3")
        # print("debug" + ": " + start_time_formatted + ", " + end_time_formatted + ", " + output_file)
        command = f"ffmpeg -y -i {mp3_path} -ss {start_time_formatted} -to {end_time_formatted} -c copy {output_file}"
        subprocess.run(command, shell=True)
    # 最後の区間を処理
    if len(timestamps) > 1:
        start_time = timestamps[-1]
        start_time_formatted = f"{start_time[:2]}:{start_time[2:4]}:{start_time[4:]}"
        output_file = os.path.join(output_dir, f"{start_time}.mp3")
        command = f"ffmpeg -y -i {mp3_path} -ss {start_time_formatted} -c copy {output_file}"
        subprocess.run(command, shell=True)

def convert_movie_file_to_mp3(movie_file):
    # ローカルの動画ファイルをmp3に変換する関数
    mp3_filename = convert_to_mp3(movie_file)
    return mp3_filename

def transcribe_all_mp3s_in_directory(directory):
    # 処理開始時点の記録
    with open("./debug_log.txt", 'a', encoding='utf-8') as log_file:
        log_file.write(f"{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')} - transcribe 開始: {directory}\n")
    
    print("MP3ファイルをテキストに変換中...")
    mp3_files = [f for f in sorted(os.listdir(directory)) if f.endswith('.mp3')]
    
    if not mp3_files:
        print("MP3ファイルが見つかりませんでした。")
        return

    for file in mp3_files:
        file_path = os.path.join(directory, file)
        timestamp = file.split('.')[0]
        try:
            transcribed_text = transcribe_mp3(file_path, timestamp=timestamp, dirname=directory)
            save_transcription(transcribed_text, timestamp=timestamp, dirname=directory)
            print(f"{file} の変換が完了しました。")
        except Exception as e:
            print(f"{file} の変換中にエラーが発生しました: {e}")
            # エラーをログに記録
            with open("./debug_log.txt", 'a', encoding='utf-8') as log_file:
                log_file.write(f"{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')} - エラー: {file} - {str(e)}\n")
            continue  # 次のファイルの処理に進む

    print("すべてのMP3ファイルの処理が完了しました。")
    # 処理終了時点の記録
    with open("./debug_log.txt", 'a', encoding='utf-8') as log_file:
        log_file.write(f"{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')} - transcribe 終了: {directory}\n")


def load_api_key():
    # config.yamlからAPIキーを読み込む関数
    with open("config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    return config['openai_api_key']

def transcribe_mp3(file_path, timestamp=None, dirname=''):
    # Initialize the OpenAI client
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    attempts = 0
    max_retries=3
    wait_time=5
    while attempts < max_retries:
        try:
            # 処理開始時点の記録
            with open("./debug_log.txt", 'a', encoding='utf-8') as log_file:
                log_file.write(f"{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')} - openai 開始: {file_path}\n")
            
            # Open the MP3 file and transcribe it using the OpenAI API
            with open(file_path, 'rb') as mp3_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=mp3_file
                )
                # Retrieve the transcription text from the response
                transcribed_text = transcript.text  # Access the text attribute
                
                # サーバーから帰ってきたテキストの記録
                with open("./debug_log.txt", 'a', encoding='utf-8') as log_file:
                    log_file.write(f"{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')} - 結果: {transcribed_text}\n")
                
                return transcribed_text
        except Exception as e:
            attempts += 1
            print(f"Retry {attempts}/{max_retries} after error: {e}")
            time.sleep(wait_time)

    raise Exception("Failed to transcribe after multiple attempts")

def save_transcription(text, timestamp=None, dirname=''):
    filename = f"./tmp/{timestamp}.txt"
    
    # テキストファイルとして保存
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(text)
    print(f"Transcription saved to {filename}")
    
import re

def extract_video_id(url):
    # YouTubeのURLからVIDEO IDを抽出する関数
    patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([^&]+)',
        r'(?:https?://)?youtu\.be/([^?&]+)',
        r'(?:https?://)?m\.youtube\.com/watch\?v=([^&]+)',
        r'(?:https?://)?m\.youtube\.com/embed/([^?&]+)',
        r'(?:https?://)?www\.youtube\.com/watch\?v=([^&]+)&app=mobile',
        r'(?:https?://)?m\.youtube\.com/watch\?v=([^&]+)&feature=youtu\.be',
        r'youtube://watch\?v=([^&]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def main():
    if len(sys.argv) == 1:
        with open("videos.txt", 'r') as file:
            lines = file.readlines()

        for line in lines:
            parts = line.strip().split()
            if len(parts) == 0:
                continue

            video_source = parts[0]
            interval_sec = int(parts[1]) if len(parts) > 1 else 30

            if video_source.startswith("https://") or video_source.startswith("http://") or video_source.startswith("youtube://"):
                youtube_url = video_source
                video_id = extract_video_id(youtube_url)  # VIDEO IDを抽出

                if video_id is None:
                    print("無効なYouTube URLです。")
                    continue

                print("動画ダウンロード開始")
                video_filename, video_title = download_video(youtube_url)
                print(f"動画タイトル: {video_title}")
                print("フレーム抽出開始")
                extract_frames(video_filename, interval_sec, output_dir="./tmp")
                print("字幕ダウンロード開始")
                download_subtitles(video_id, output_dir="./tmp")

                if not os.path.exists("./post"):
                    os.makedirs("./post")
                result_filename = f"./post/[youtube]{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
                process_output_files("./tmp", result_filename, youtube_url, video_title)

                os.remove(video_filename)
                print(f"Deleted temporary video file: {video_filename}")

            else:
                movie_file = video_source

                print("フレーム抽出開始")
                extract_frames(movie_file, interval_sec, output_dir="./tmp")
                print("動画をmp3に変換中...")
                mp3_filename = convert_movie_file_to_mp3(movie_file)
                print("mp3変換完了")

                timestamps = []
                for file in sorted(os.listdir("./tmp")):
                    if file.endswith('.png'):
                        timestamps.append(file.split('-')[0])

                print("音声ファイルを分割中...")
                print(timestamps)
                split_audio(mp3_filename, timestamps, output_dir="./tmp")
                print("音声ファイル分割完了")

                transcribe_all_mp3s_in_directory("./tmp")

                if not os.path.exists("./post"):
                    os.makedirs("./post")
                result_filename = f"./post/[movie]{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
                process_output_files("./tmp", result_filename, movie_file, movie_file)

            for file in os.listdir("./tmp"):
                file_path = os.path.join("./tmp", file)
                os.remove(file_path)
            print("Deleted all temporary files in ./tmp")

    elif len(sys.argv) in [2, 3]:
        if sys.argv[1].startswith("https://") or sys.argv[1].startswith("http://") or sys.argv[1].startswith("youtube://"):
            youtube_url = sys.argv[1]
            interval_sec = int(sys.argv[2]) if len(sys.argv) == 3 else 10
            video_id = extract_video_id(youtube_url)  # VIDEO IDを抽出

            if video_id is None:
                print("無効なYouTube URLです。")
                sys.exit(1)

            print("動画ダウンロード開始")
            video_filename, video_title = download_video(youtube_url)
            print(f"動画タイトル: {video_title}")
            print("フレーム抽出開始")
            extract_frames(video_filename, interval_sec, output_dir="./tmp")
            print("字幕ダウンロード開始")
            download_subtitles(video_id, output_dir="./tmp")

            if not os.path.exists("./post"):
                os.makedirs("./post")
            result_filename = f"./post/[youtube]{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
            process_output_files("./tmp", result_filename, youtube_url, video_title)

            os.remove(video_filename)
            print(f"Deleted temporary video file: {video_filename}")

        else:
            movie_file = sys.argv[1]
            interval_sec = int(sys.argv[2]) if len(sys.argv) == 3 else 10

            print("フレーム抽出開始")
            extract_frames(movie_file, interval_sec, output_dir="./tmp")
            print("動画をmp3に変換中...")
            mp3_filename = convert_movie_file_to_mp3(movie_file)
            print("mp3変換完了")

            timestamps = []
            for file in sorted(os.listdir("./tmp")):
                if file.endswith('.png'):
                    timestamps.append(file.split('-')[0])

            print("音声ファイルを分割中...")
            print(timestamps)
            split_audio(mp3_filename, timestamps, output_dir="./tmp")
            print("音声ファイル分割完了")

            transcribe_all_mp3s_in_directory("./tmp")

            if not os.path.exists("./post"):
                os.makedirs("./post")
            result_filename = f"./post/[movie]{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
            process_output_files("./tmp", result_filename, movie_file, movie_file)

        for file in os.listdir("./tmp"):
            file_path = os.path.join("./tmp", file)
            os.remove(file_path)
        print("Deleted all temporary files in ./tmp")

    else:
        print("Usage: python create_youtubemd.py <youtube url> [interval_sec] or python create_youtubemd.py")
        sys.exit(1)

if __name__ == "__main__":
    if not os.path.exists("./tmp"):
        os.makedirs("./tmp")

    main()
