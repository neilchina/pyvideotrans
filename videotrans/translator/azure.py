# -*- coding: utf-8 -*-
import re
import time
import httpx
from openai import AzureOpenAI
from videotrans.configure import config
from videotrans.util import tools

def trans(text_list, target_language="English", *, set_p=True):
    """
    text_list:
        可能是多行字符串，也可能是格式化后的字幕对象数组
    target_language:
        目标语言
    set_p:
        是否实时输出日志，主界面中需要
    """
    proxies = None
    serv = tools.set_proxy()
    if serv:
        proxies = {
            'http://': serv,
            'https://': serv
        }

    # 翻译后的文本
    target_text = []
    # 整理待翻译的文字为 List[str]
    if isinstance(text_list, str):
        source_text = text_list.strip().split("\n")
    else:
        source_text = [t['text'] for t in text_list]

    client = AzureOpenAI(
        api_key=config.params["azure_key"],
        api_version="2023-05-15",
        azure_endpoint=config.params["azure_api"],  # Your Azure OpenAI resource's endpoint value.
        http_client=httpx.Client(proxies=proxies)
    )
    split_size = int(config.settings['trans_thread'])
    split_source_text = [source_text[i:i + split_size] for i in range(0, len(source_text), split_size)]

    for it in split_source_text:
        try:
            source_length = len(it)
            print(f'{source_length=}')
            message = [
                {'role': 'system',
                 'content': config.params["azure_template"].replace('{lang}', target_language)},
                {'role': 'user', 'content': "\n".join(it)},
            ]

            config.logger.info(f"\n[Azure start]待翻译:{message=}")
            response = client.chat.completions.create(
                model=config.params["azure_model"],
                messages=message
            )

            config.logger.info(f'Azure 返回响应:{response}')
            if response.choices:
                result = response.choices[0].message.content.strip()
            elif response.data and response.data['choices']:
                result = response.data['choices'][0]['message']['content'].strip()
            else:
                raise Exception(f"[error]:Azure {response}")
            result=result.strip().replace('&#39;','"').split("\n")
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
            error = str(e)
            if re.search(r'Rate limit', error, re.I) is not None:
                if set_p:
                    tools.set_process(f'Azure limit rate, wait 30s')
                time.sleep(30)
                return trans(text_list, target_language, set_p=set_p)
            else:
                raise Exception(f'Azure error:{str(error)}')
    if isinstance(text_list, str):
        return "\n".join(target_text)

    max_i = len(target_text)
    for i, it in enumerate(text_list):
        if i < max_i:
            text_list[i]['text'] = target_text[i]
    return text_list
