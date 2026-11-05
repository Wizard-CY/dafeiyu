"""Open y.qq.com in Edge, wait for login, and import the full cookie."""

import json
import time
import urllib.request

from playwright.sync_api import sync_playwright

BACKEND = 'http://127.0.0.1:3311/login/cookie'
PROFILE = r'D:\JingJing\backend/qqmusic\browser_profile'


def post_cookie(cookie):
    body = json.dumps({'cookie': cookie}).encode()
    request = urllib.request.Request(BACKEND, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            PROFILE,
            channel='msedge',
            headless=False,
            args=['--start-maximized', '--no-first-run'],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto('https://y.qq.com', timeout=60000)
        print('请在打开的 Edge 窗口里登录 y.qq.com（用 QQ 扫码）', flush=True)
        deadline = time.time() + 15 * 60
        while time.time() < deadline:
            cookies = context.cookies()
            names = {item['name']: item['value'] for item in cookies if 'qq.com' in item.get('domain', '')}
            if names.get('qm_keyst') and (names.get('uin') or names.get('qqmusic_uin')):
                cookie = '; '.join('%s=%s' % (item['name'], item['value']) for item in cookies if 'qq.com' in item.get('domain', ''))
                with open(r'D:\JingJing\backend/qqmusic\browser_cookie.txt', 'w', encoding='utf-8') as handle:
                    handle.write(cookie)
                print('发现登录 cookie，长度', len(cookie), flush=True)
                result = post_cookie(cookie)
                print('导入结果', result, flush=True)
                time.sleep(8)
                context.close()
                return
            time.sleep(3)
        print('等待超时，没有抓到 qm_keyst', flush=True)
        context.close()


if __name__ == '__main__':
    main()
