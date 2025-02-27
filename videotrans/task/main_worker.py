# -*- coding: utf-8 -*-
import os
import time
from PySide6.QtCore import QThread
from pydub import AudioSegment

from videotrans.configure import config
from videotrans.task.trans_create import TransCreate
from videotrans.tts import text_to_speech
from videotrans.util.tools import set_process, delete_temp, get_subtitle_from_srt, pygameaudio, speed_up_mp3,send_notification


class Worker(QThread):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.video = None

    def run(self) -> None:
        task_nums = len(config.queue_task)
        objs=[]
        for (i,it) in enumerate(config.queue_task):
            t=TransCreate(it)
            set_process(t.btnkey, 'add_process')
            objs.append(t)
        num = 0
        while len(objs)>0:
            num += 1
            set_process(f"Processing {num}/{task_nums}", 'statusbar')
            try:
                st = time.time()
                self.video = objs.pop(0)
                config.btnkey=self.video.btnkey
                set_process(config.transobj['kaishichuli'])
                self.video.run()
                # 成功完成
                config.params['line_roles'] = {}
                dur=int(time.time() - st)
                set_process(f"{self.video.target_dir}##{dur}", 'succeed')
                send_notification(config.transobj["zhixingwc"],f'{self.video.source_mp4 if self.video.source_mp4 else "subtitles -> audio"}, {dur}s')

                try:
                    if os.path.exists(self.video.novoice_mp4):
                        time.sleep(1)
                        os.unlink(self.video.novoice_mp4)
                except:
                    pass
            except Exception as e:
                print(f"mainworker {str(e)}")
                set_process(f"{str(e)}", 'error')
                send_notification("Error",f"{str(e)}")
                return
            finally:
                self.video=None
        # 全部完成
        set_process("", 'end')
        time.sleep(10)
        delete_temp(None)


class Shiting(QThread):
    def __init__(self, obj, parent=None):
        super().__init__(parent=parent)
        self.obj = obj
        self.stop = False

    def run(self):
        # 获取字幕
        try:
            subs = get_subtitle_from_srt(self.obj['sub_name'])
        except Exception as e:
            set_process(f'{config.transobj["geshihuazimuchucuo"]}:{str(e)}')
            return False
        rate = int(str(config.params["voice_rate"]).replace('%', ''))
        if rate >= 0:
            rate = f"+{rate}%"
        else:
            rate = f"{rate}%"
        # 取出每一条字幕，行号\n开始时间 --> 结束时间\n内容
        # 取出设置的每行角色
        line_roles = config.params["line_roles"] if "line_roles" in config.params else None
        for it in subs:
            if config.task_countdown <= 0 or self.stop:
                return
            if config.current_status != 'ing':
                set_process(config.transobj['tingzhile'], 'stop')
                return True
            # 判断是否存在单独设置的行角色，如果不存在则使用全局
            voice_role = config.params['voice_role']
            if line_roles and f'{it["line"]}' in line_roles:
                voice_role = line_roles[f'{it["line"]}']
            filename = self.obj['cache_folder'] + f"/{time.time()}.mp3"
            text_to_speech(text=it['text'],
                           role=voice_role,
                           rate=rate,
                           filename=filename,
                           tts_type=config.params['tts_type'],
                           set_p=False
                           )
            audio_data = AudioSegment.from_file(filename, format="mp3")
            mp3len = len(audio_data)

            wavlen = it['end_time'] - it['start_time']
            # 新配音大于原字幕里设定时长
            diff = mp3len - wavlen
            if diff > 0 and config.params["voice_autorate"]:
                speed = mp3len / wavlen if wavlen>0 else 1
                speed = round(speed, 2)
                set_process(f"dubbing speed {speed} ")
                tmp_mp3 = filename + "-speedup.mp3"
                speed_up_mp3(filename=filename, speed=speed, out=tmp_mp3)
                filename = tmp_mp3

            set_process(f'Listening:{it["text"]}')
            pygameaudio(filename)
            try:
                if os.path.exists(filename):
                    os.unlink(filename)
            except:
                pass
