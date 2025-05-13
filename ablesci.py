#!/usr/bin/env python
# cron:40 7,21 * * *
# new Env("科研通签到")
# coding=utf-8
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
import re
import random
import time
import datetime
import json
from typing import Optional, Dict, Any, List, Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from cachetools import cached, TTLCache

from sendNotify import send


def generate_interval() -> float:
    """生成1-5秒随机请求间隔"""
    return random.uniform(1, 5)


def get_headers(cookie: str) -> Dict[str, str]:
    is_mobile = random.choice([True, False])
    user_agent = generate_user_agent('mobile' if is_mobile else 'desktop')

    try:
        chrome_match = re.search(r'Chrome/(\d+\.\d+\.\d+\.\d+)', user_agent)
        chrome_version = chrome_match.group(1) if chrome_match else '125.0.0.0'
        # 同步Edge版本处理
        edge_match = re.search(r'Edg/(\d+\.\d+\.\d+\.\d+)', user_agent)
        edge_version = edge_match.group(1) if edge_match else f'{chrome_version.split(".")[0]}.0.0.0'
    except Exception as e:
        print(f"Chrome版本提取失败: {str(e)}")
        chrome_version = '125.0.0.0'

    edge_version = chrome_version.split('.')[0] + '.0.0.0'  # 统一使用Chrome主版本

    # 生成随机XFF头
    x_forwarded_for = f'{random.randint(60, 220)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}'

    headers = {
        'authority': 'www.ablesci.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'cookie': cookie,
        'dnt': str(random.randint(0, 1)),  # 随机DNT标识
        'pragma': 'no-cache',
        'referer': 'https://www.ablesci.com/',
        'sec-ch-ua': f'"Chromium";v="{chrome_version.split(".")[0]}", "Microsoft Edge";v="{edge_version.split(".")[0]}", "Not-A.Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '["Windows", "Linux", "macOS"][random.randint(0,2)]',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': user_agent,
        'x-requested-with': 'XMLHttpRequest',
        'x-forwarded-for': x_forwarded_for,
        'x-real-ip': x_forwarded_for
    }
    
    # 随机化headers顺序
    keys = list(headers.keys())
    random.shuffle(keys)
    
    return {k: headers[k] for k in keys}


def create_session(retries: int = 3) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def ablesci(cookie: str) -> Dict[str, Any]:
    url = "https://www.ablesci.com/user/sign"
    session = create_session()
    try:
        response = session.get(url, headers=get_headers(cookie), timeout=10)
        response.raise_for_status()
        print("成功访问签到接口")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {str(e)}")
        return {'code': -1, 'msg': '网络请求失败'}


def ablesci_index(cookie: str) -> str:
    url = "https://www.ablesci.com/my/home"
    session = create_session()
    try:
        response = session.get(url, headers=get_headers(cookie), timeout=10)
        response.raise_for_status()
        html = response.text

        links = re.findall(r'<title.*?>(.+?)</title>', html)
        links2 = re.findall(r'<span style="color: #FF7200;.*?>(.+?)</span>', html)
        return f"{''.join(links)}{''.join(links2)}\n"
    except requests.exceptions.RequestException as e:
        print(f"主页请求失败: {str(e)}")
        return ""


def cookies() -> Iterator[str]:
    """
    从环境变量解析科研通多账号cookie配置

    环境变量要求:
    - 使用ABLESCICOOKIE环境变量存储多个cookie
    - 支持两种格式：
        1. cookie数字=真实cookie内容（如cookie1=x1234...）
        2. 原始cookie格式（如security_session_verify=值; other_cookie=值）
    - 多个配置间用换行符分隔

    返回值:
        Iterator[str]: 生成器，逐个返回有效cookie字符串

    异常处理:
    - 自动跳过空行和无效格式条目
    - 使用正则表达式r'^(cookie\\d+=)?(.+?)$'匹配带前缀和不带前缀的cookie
    - 无效条目会记录warning级别日志
    """
    import re
    cookie_env = os.environ.get('ABLESCICOOKIE', '')
    if not cookie_env.strip():
        print("\033[31m[严重错误] 环境变量ABLESCICOOKIE未设置或为空！\033[0m")
        return
    cookies = cookie_env.splitlines()
    pattern = re.compile(r'^(cookie\d+=)?(.+?)$', re.MULTILINE)
    
    for entry in cookies:
        entry = entry.strip()
        if not entry:
            continue
        match = pattern.search(entry)
        if match:
            # 提取分组2的内容（原始cookie）或分组1（无前缀时整个匹配）
            yield match.group(2).strip() if match.group(2) else match.group(1).strip()
        else:
            print(f"[警告] Cookie格式错误: {entry}")





# 缓存配置（1小时更新）
ua_cache = TTLCache(maxsize=100, ttl=3600)

@cached(ua_cache)
def generate_user_agent(platform: str) -> str:
    templates = {
        "desktop": {
            "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36",
            "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{major_version}.0) Gecko/20100101 Firefox/{major_version}.0",
            "edge": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36 Edg/{major_version}.0.0.0"
        },
        "mobile": {
            "chrome": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Mobile Safari/537.36",
            "firefox": "Mozilla/5.0 (Android 13; Mobile; rv:{major_version}.0) Gecko/{major_version}.0 Firefox/{major_version}.0",
            "edge": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Mobile Safari/537.36 EdgA/{major_version}.0.0.0"
        }
    }
    try:
        current_year = datetime.datetime.now().year
        major_version = random.randint(120, current_year - 2010 + 120)
        
        templates = {
            'desktop': {
                'chrome': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36',
                'firefox': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{major_version}.0) Gecko/20100101 Firefox/{major_version}.0',
                'edge': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36 Edg/{major_version}.0.0.0'
            },
            'mobile': {
                'chrome': f'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Mobile Safari/537.36',
                'firefox': f'Mozilla/5.0 (Android 13; Mobile; rv:{major_version}.0) Gecko/{major_version}.0 Firefox/{major_version}.0',
                'edge': f'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Mobile Safari/537.36 EdgA/{major_version}.0.0.0'
            }
        }
        
        browser_type = random.choice(['chrome', 'firefox', 'edge'])
        return templates[platform][browser_type]
    except Exception as e:
        print(f"UA生成异常: {str(e)}")
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

def extract_chinese(html_content: str) -> str:
    try:  
        # 匹配所有<p>标签内容
        paragraphs = re.findall(r'<(?:p|div)[^>]*>(.*?)</(?:p|div)>', html_content, flags=re.IGNORECASE | re.DOTALL)
        
        # 对每个段落单独处理
        chinese_pattern = re.compile(r'[\u4e00-\u9fa5\d，。！？；：、（）《》【】「」“”‘’—…a-zA-Z.]+')
        cleaned_paragraphs = [
            ''.join(chinese_pattern.findall(re.sub(r'<[^>]+>', '', p)))
            for p in paragraphs
        ]
        
        # 用换行符连接有效段落
        return '\n'.join([p for p in cleaned_paragraphs if p])
    
    except Exception as e:
        print(f'处理失败：{str(e)}')
        return ''



if __name__ == "__main__":
    content = "="*26 + "\n"
    cookies_found = False
    for cookie in cookies():
        if not cookie:
            continue
        cookies_found = True

        interval = generate_interval()
        time.sleep(interval)

        result = ablesci(cookie)
        profile = ablesci_index(cookie)

        content += f"{profile}今日科研通签到:\n{result.get('msg', '')}\n"

        if result.get('code') == 0:
            content += extract_chinese(f"{result['data']['today_history']}")+ "\n"
        else:
            print("签到失败")

        time.sleep(interval)

    if not cookies_found:
        content += "\033[31m[错误] 未找到任何有效的cookie配置，请检查环境变量ABLESCICOOKIE是否正确设置\033[0m\n"
    
    content += "="*26
    print(content)
    send("科研通签到", content)