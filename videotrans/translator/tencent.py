import json
import re
import time

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tmt.v20180321 import tmt_client, models
from videotrans.configure import config
from videotrans.util import tools

def trans(text_list, target_language="en", *, set_p=True):
    """
    text_list:
        可能是多行字符串，也可能是格式化后的字幕对象数组
    target_language:
        目标语言
    set_p:
        是否实时输出日志，主界面中需要
    """

    # 翻译后的文本
    target_text = []
    # 整理待翻译的文字为 List[str]
    if isinstance(text_list, str):
        source_text = text_list.strip().split("\n")
    else:
        source_text = [t['text'] for t in text_list]

    # 切割为每次翻译多少行，值在 set.ini中设定，默认10
    split_size = int(config.settings['trans_thread'])
    split_source_text = [source_text[i:i + split_size] for i in range(0, len(source_text), split_size)]

    cred = credential.Credential(config.params['tencent_SecretId'], config.params['tencent_SecretKey'])
    # 实例化一个http选项，可选的，没有特殊需求可以跳过
    httpProfile = HttpProfile()
    httpProfile.endpoint = "tmt.tencentcloudapi.com"

    # 实例化一个client选项，可选的，没有特殊需求可以跳过
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    # 实例化要请求产品的client对象,clientProfile是可选的
    client = tmt_client.TmtClient(cred, "ap-beijing", clientProfile)

    for it in split_source_text:
        try:
            # 实例化一个请求对象,每个接口都会对应一个request对象
            source_length = len(it)
            print(f'{source_length=}')
            req = models.TextTranslateRequest()
            params = {
                "SourceText": "\n".join(it),
                "Source": "auto",
                "Target": target_language,
                "ProjectId": 0
            }
            req.from_json_string(json.dumps(params))
            # 返回的resp是一个TextTranslateResponse的实例，与请求对象对应
            resp = client.TextTranslate(req)
            result = resp.TargetText.strip().replace('&#39;','"').split("\n")#json.loads(resp.TargetText)
            if set_p:
                tools.set_process("\n\n".join(result), 'subtitle')
            result_length = len(result)
            print(f'{result_length=}')
            while result_length < source_length:
                result.append("")
                result_length += 1
            result = result[:source_length]
            target_text.extend(result)
        except Exception as e:
            err = str(e)
            if re.search(r'LimitExceeded', err, re.I):
                if set_p:
                    tools.set_process("超出腾讯翻译频率或配额限制，暂停5秒")
                time.sleep(10)
                return trans(text_list, target_language, set_p=set_p)
            config.logger.error("tencent api error:" + str(e))
            if set_p:
                tools.set_process("[error]腾讯翻译失败:" + str(e))
            return "tencent api error:" + str(e)

    if isinstance(text_list, str):
        return "\n".join(target_text)

    max_i = len(target_text)
    for i, it in enumerate(text_list):
        if i < max_i:
            text_list[i]['text'] = target_text[i]
    return text_list
