"""Проверка настоящего lab2.exe в отдельных консолях Windows (Python 3).

Запуск: py -3 tests/run_tests.py
Снимки двух окон: py -3 tests/run_tests.py --screenshots
Используется только стандартная библиотека Python.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import zlib


class Coord(c.Structure):
    _fields_ = [('x', c.c_short), ('y', c.c_short)]


class SmallRect(c.Structure):
    _fields_ = [('left', c.c_short), ('top', c.c_short),
                ('right', c.c_short), ('bottom', c.c_short)]


class Char(c.Union):
    _fields_ = [('unicode', w.WCHAR), ('ascii', c.c_char)]


class Key(c.Structure):
    _fields_ = [('down', w.BOOL), ('repeat', w.WORD), ('vk', w.WORD),
                ('scan', w.WORD), ('char', Char), ('state', w.DWORD)]


class Event(c.Union):
    _fields_ = [('key', Key), ('padding', c.c_byte * 16)]


class Input(c.Structure):
    _fields_ = [('type', w.WORD), ('event', Event)]


k = c.WinDLL('kernel32', use_last_error=True)
c.WinDLL('user32').SetProcessDPIAware()
k.CreateFileW.restype = w.HANDLE
k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p,
                         w.DWORD, w.DWORD, w.HANDLE]
k.CloseHandle.argtypes = [w.HANDLE]
k.AttachConsole.argtypes = [w.DWORD]
k.SetConsoleScreenBufferSize.argtypes = [w.HANDLE, Coord]
k.SetConsoleWindowInfo.argtypes = [w.HANDLE, w.BOOL, c.POINTER(SmallRect)]
k.ReadConsoleOutputCharacterW.argtypes = [w.HANDLE, w.LPWSTR, w.DWORD,
                                         Coord, c.POINTER(w.DWORD)]
k.WriteConsoleInputW.argtypes = [w.HANDLE, c.POINTER(Input), w.DWORD,
                                c.POINTER(w.DWORD)]
k.GetConsoleWindow.restype = w.HWND


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_screen(handle):
    buffer = c.create_unicode_buffer(20000)
    count = w.DWORD()
    check(k.ReadConsoleOutputCharacterW(handle, buffer, 20000,
                                        Coord(0, 0), c.byref(count)),
          'Не удалось прочитать консоль')
    return buffer[:count.value]


def enter_line(handle, source):
    characters = source + '\r'
    events = (Input * len(characters))()
    for i, char in enumerate(characters):
        events[i].type = 1
        events[i].event.key.down = True
        events[i].event.key.repeat = 1
        events[i].event.key.char.unicode = char
        events[i].event.key.vk = 13 if char == '\r' else 0
    count = w.DWORD()
    check(k.WriteConsoleInputW(handle, events, len(events), c.byref(count)),
          'Не удалось передать строку в консоль')
    check(count.value == len(events), 'Введена не вся строка')


def save_window_png(path):
    """Сохранить пиксели настоящего окна консоли без дорисовки текста."""
    user = c.WinDLL('user32', use_last_error=True)
    gdi = c.WinDLL('gdi32', use_last_error=True)
    user.GetWindowDC.restype = w.HDC
    user.GetWindowDC.argtypes = [w.HWND]
    user.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
    user.ShowWindow.argtypes = [w.HWND, c.c_int]
    user.PrintWindow.argtypes = [w.HWND, w.HDC, w.UINT]
    user.ReleaseDC.argtypes = [w.HWND, w.HDC]
    gdi.CreateCompatibleDC.argtypes = [w.HDC]
    gdi.CreateCompatibleDC.restype = w.HDC
    gdi.CreateCompatibleBitmap.argtypes = [w.HDC, c.c_int, c.c_int]
    gdi.CreateCompatibleBitmap.restype = w.HBITMAP
    gdi.SelectObject.argtypes = [w.HDC, w.HANDLE]
    gdi.SelectObject.restype = w.HANDLE
    gdi.DeleteObject.argtypes = [w.HANDLE]
    gdi.DeleteDC.argtypes = [w.HDC]
    gdi.GetDIBits.argtypes = [w.HDC, w.HBITMAP, w.UINT, w.UINT,
                             c.c_void_p, c.c_void_p, w.UINT]

    window = k.GetConsoleWindow()
    check(window, 'У консоли нет окна для снимка')
    user.ShowWindow(window, 5)
    time.sleep(0.25)
    rect = w.RECT()
    check(user.GetWindowRect(window, c.byref(rect)), 'Не прочитан размер окна')
    width, height = rect.right - rect.left, rect.bottom - rect.top
    check(width > 0 and height > 0, 'Окно консоли не имеет видимого размера')
    window_dc = user.GetWindowDC(window)
    memory_dc = gdi.CreateCompatibleDC(window_dc)
    bitmap = gdi.CreateCompatibleBitmap(window_dc, width, height)
    previous = gdi.SelectObject(memory_dc, bitmap)
    try:
        check(user.PrintWindow(window, memory_dc, 2), 'PrintWindow не создал снимок')
        gdi.SelectObject(memory_dc, previous)
        header = struct.pack('<IiiHHIIiiII', 40, width, -height,
                             1, 32, 0, 0, 0, 0, 0, 0)
        info = c.create_string_buffer(header)
        pixels = c.create_string_buffer(width * height * 4)
        check(gdi.GetDIBits(memory_dc, bitmap, 0, height, pixels, info, 0) == height,
              'Не прочитаны пиксели окна')
        rows = []
        raw = pixels.raw
        for y in range(height):
            row = raw[y * width * 4:(y + 1) * width * 4]
            rgb = bytearray(width * 3)
            rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
            rows.append(b'\0' + rgb)

        def chunk(kind, payload):
            return (struct.pack('>I', len(payload)) + kind + payload
                    + struct.pack('>I', zlib.crc32(kind + payload)))

        png = b'\x89PNG\r\n\x1a\n'
        png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        png += chunk(b'IDAT', zlib.compress(b''.join(rows)))
        png += chunk(b'IEND', b'')
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(png)
    finally:
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory_dc)
        user.ReleaseDC(window, window_dc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    executable = root / 'code/lab2.exe'
    check(executable.is_file(), 'Сначала выполните code/build.bat')
    sources = ['', 'a', 'ab', 'abc', 'abcd', 'aba', 'aaaa', 'a b', ' a ',
               'Ab1!', 'тест', 'а роза', 'abc' * 85, 'a' * 256, 'b' * 300]
    error_text = 'Error: input failed or string is longer than 255 characters.'
    screenshots = {11: '11-russian.png', 14: '14-too-long.png'}
    results = []
    for number, source in enumerate(sources, 1):
        k.FreeConsole()
        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        process = subprocess.Popen([str(executable)],
                                   creationflags=subprocess.CREATE_NEW_CONSOLE,
                                   startupinfo=startup)
        input_handle = output_handle = None
        try:
            for _ in range(300):
                if k.AttachConsole(process.pid):
                    break
                time.sleep(0.01)
            else:
                raise RuntimeError('Не удалось подключиться к консоли программы')
            input_handle = k.CreateFileW('CONIN$', 0xC0000000, 3, None, 3, 0, None)
            output_handle = k.CreateFileW('CONOUT$', 0xC0000000, 3, None, 3, 0, None)
            window_rect = SmallRect(0, 0, 79, 7)
            check(k.SetConsoleWindowInfo(output_handle, True, c.byref(window_rect)),
                  'Не установлен размер окна консоли')
            check(k.SetConsoleScreenBufferSize(output_handle, Coord(100, 200)),
                  'Не установлен размер буфера консоли')
            window_rect = SmallRect(0, 0, 99, 7)
            check(k.SetConsoleWindowInfo(output_handle, True, c.byref(window_rect)),
                  'Не установлена ширина окна консоли')
            for _ in range(300):
                if 'Enter a string' in read_screen(output_handle):
                    break
                time.sleep(0.01)
            else:
                raise RuntimeError('Программа не вывела приглашение')

            enter_line(input_handle, source)
            process.wait(timeout=5)
            screen = read_screen(output_handle)
            expected = source + source[::-1] if len(source) <= 255 else error_text
            expected_exit = 0 if len(source) <= 255 else 1
            check(process.returncode == expected_exit, 'Неверный код завершения')
            if expected_exit == 0:
                start = screen.index('Palindrome: ') + len('Palindrome: ')
                actual = screen[start:start + len(expected)]
                check(actual == expected, 'Результат отличается от ожидаемого')
                check(screen[start + len(expected)] == ' ', 'Лишние символы в результате')
                check(actual == actual[::-1], 'Результат не является палиндромом')
                check(len(actual) == 2 * len(source), 'Неверная длина результата')
            else:
                check(error_text in screen, 'Нет сообщения об ошибке')
                check('Palindrome:' not in screen, 'При ошибке выведен результат')
                actual = error_text

            rows = [screen[i:i+100].rstrip() for i in range(0, len(screen), 100)]
            console = '\n'.join(row for row in rows if row)
            result = {'test': number, 'input': source, 'input_length': len(source),
                      'expected': expected, 'actual': actual,
                      'exit_code': process.returncode, 'console': console, 'passed': True}
            if args.screenshots and number in screenshots:
                check(k.SetConsoleWindowInfo(output_handle, True, c.byref(window_rect)),
                      'Не восстановлено начало видимой области консоли')
                screenshot = root / 'tests/screenshots' / screenshots[number]
                save_window_png(screenshot)
                result['screenshot'] = screenshot.relative_to(root).as_posix()
            results.append(result)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            if input_handle is not None:
                k.CloseHandle(input_handle)
            if output_handle is not None:
                k.CloseHandle(output_handle)
            k.FreeConsole()

    target = root / 'tests'
    metadata = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                'command': subprocess.list2cmdline([sys.executable, *sys.argv]),
                'reproduce_command': 'py -3 tests/run_tests.py' + (' --screenshots' if args.screenshots else ''),
                'source_sha256': hashlib.sha256((root/'code/main.asm').read_bytes()).hexdigest(),
                'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
                'passed': len(results), 'total': len(sources)}
    (target/'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (target/'run-info.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lines = ['Результаты проверки lab2.exe.',
             f'Пройдено: {len(results)} из {len(sources)}.',
             'Кавычки показывают границы строк и сохраняемые пробелы.', '']
    for number, result in enumerate(results, 1):
        (target/f'console-{number:02d}.txt').write_text(result['console']+'\n', encoding='utf-8')
        lines.extend([f'ТЕСТ {number}', 'INPUT: ' + json.dumps(result['input'], ensure_ascii=False),
                      'EXPECTED: ' + json.dumps(result['expected'], ensure_ascii=False),
                      'ACTUAL: ' + json.dumps(result['actual'], ensure_ascii=False),
                      'EXIT: ' + str(result['exit_code']), result['console'], 'CHECK: PASS', ''])
    (root/'code/tests.txt').write_text('\n'.join(lines), encoding='utf-8')
    print(f'PASS: {len(results)}/{len(sources)} console tests')


if __name__ == '__main__':
    main()
