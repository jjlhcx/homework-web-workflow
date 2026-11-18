"""学习通草稿助手。只暂存，不提交。"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import re
import subprocess
import threading
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor'))


class TaskError(Exception):
    pass


def validate_endpoint(endpoint):
    try:
        parsed = urlparse(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise TaskError('INVALID_ENDPOINT: expected local HTTP host and port') from exc
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or not port or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise TaskError('INVALID_ENDPOINT: only a local HTTP debugging port is supported')
    return port


def build_changes(snapshot: dict, plan: dict) -> list[dict]:
    if not isinstance(plan, dict):
        raise TaskError('INVALID_PLAN: expected object')
    for key in ('course_id', 'work_id'):
        if not plan.get(key) or str(plan[key]) != str(snapshot.get(key)):
            raise TaskError(f'IDENTITY_MISMATCH: {key}')
    if not snapshot.get('editable'):
        raise TaskError('READ_ONLY: completed or unsupported page')
    answers = plan.get('answers')
    if not isinstance(answers, dict) or not answers:
        raise TaskError('INVALID_PLAN: answers must be a nonempty object')
    questions = {q['id']: q for q in snapshot['questions']}
    changes = []
    for qid, answer in answers.items():
        if qid not in questions:
            raise TaskError(f'UNKNOWN_QUESTION: {qid}')
        q = questions[qid]
        if q.get('has_assets'):
            raise TaskError(f'ASSETS_PRESENT: {qid}')
        if q.get('manual_only'):
            raise TaskError(f'MANUAL_TASK: {qid}')
        if not isinstance(answer, dict):
            raise TaskError(f'INVALID_ANSWER: {qid}')
        if answer.get('fingerprint') and answer['fingerprint'] != q.get('fingerprint'):
            raise TaskError(f'QUESTION_CHANGED: {qid}')
        kind, current = q['kind'], q['answer']
        if kind == 'text':
            target = answer.get('text')
            if not isinstance(target, str) or not target.strip():
                raise TaskError(f'INVALID_TEXT: {qid}')
            target = target.strip()
            if current and current != target:
                raise TaskError(f'ANSWER_CONFLICT: {qid}')
        elif kind == 'blanks':
            target = answer.get('blanks')
            if not isinstance(target, list) or len(target) != len(current):
                raise TaskError(f'BLANK_COUNT: {qid}')
            if not all(isinstance(v, str) and v.strip() for v in target):
                raise TaskError(f'INVALID_BLANK: {qid}')
            target = [v.strip() for v in target]
            if any(old and old != new for old, new in zip(current, target)):
                raise TaskError(f'ANSWER_CONFLICT: {qid}')
        elif kind == 'choice':
            target = answer.get('choices')
            valid = {o['id'] for o in q['options']}
            if (not isinstance(target, list) or not target or
                    not all(isinstance(v, str) and v in valid for v in target) or
                    len(set(target)) != len(target) or
                    (not q.get('multiple') and len(target) != 1)):
                raise TaskError(f'INVALID_CHOICES: {qid}')
            if not set(current).issubset(target):
                raise TaskError(f'ANSWER_CONFLICT: {qid}')
            if set(current) == set(target):
                continue
        else:
            raise TaskError(f'UNSUPPORTED_QUESTION: {qid}')
        if current != target:
            changes.append({'id': qid, 'kind': kind, 'value': target, 'before': current})
    return changes


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest_question(question):
    data = {k: question.get(k) for k in ('stem', 'kind', 'options', 'images')}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def question_summary(snapshot):
    questions = snapshot.get('questions', [])
    kinds = {}
    unsupported = []
    for question in questions:
        kind = question['kind']
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == 'unsupported':
            unsupported.append(question['id'])
    if not questions or len(unsupported) == len(questions):
        raise TaskError('UNSUPPORTED_LAYOUT: no supported questions parsed; inspect local questions.json')
    return {'parse_status': 'partial' if unsupported else 'complete',
            'kinds': kinds, 'unsupported_questions': unsupported}


def equivalent(a, b, kind):
    return isinstance(a, list) and isinstance(b, list) and set(a) == set(b) if kind == 'choice' else a == b


def verify_plan(snapshot, plan):
    changes = build_changes(snapshot, plan)
    if changes:
        raise TaskError('ANSWER_MISMATCH: ' + ','.join(c['id'] for c in changes))
    for q in snapshot['questions']:
        if q['id'] in plan['answers'] and not equivalent(q['answer'], q.get('form_answer'), q['kind']):
            raise TaskError(f'FIELD_MISMATCH: {q["id"]}')


ADAPTER = (ROOT / 'page.js').read_text(encoding='utf-8') if (ROOT / 'page.js').exists() else ''


class Browser:
    def __init__(self, endpoint='http://127.0.0.1:9222', timeout=15000):
        validate_endpoint(endpoint)
        self.endpoint, self.timeout, self.pw = endpoint, timeout, None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise TaskError('DEPENDENCY_MISSING: run setup.ps1 once') from exc
        self.pw = sync_playwright().start()
        try:
            self.browser = self.pw.chromium.connect_over_cdp(self.endpoint, timeout=self.timeout)
            for context in self.browser.contexts:
                context.set_default_timeout(self.timeout)
        except Exception as exc:
            self.pw.stop()
            raise TaskError('BROWSER_UNAVAILABLE: use cx.ps1 open, then log in if needed') from exc
        return self

    def __exit__(self, *_):
        # Disconnect this client only; never close the user's browser.
        self.pw.stop()

    def call(self, frame, method, arg=None):
        return frame.evaluate('(arg)=>{const a=' + ADAPTER + ';return a.' + method + '(arg)}', arg)

    def snapshot(self, frame):
        data = self.call(frame, 'read')
        for q in data['questions']:
            q['fingerprint'] = digest_question(q)
        return data

    def candidates(self):
        for context in self.browser.contexts:
            for page in context.pages:
                for frame in page.frames:
                    url = urlparse(frame.url)
                    if (url.hostname or '').endswith('.chaoxing.com') and '/work/' in url.path and not url.path.endswith('/list'):
                        yield page, frame

    def target(self, course, work):
        found = []
        for page, frame in self.candidates():
            try:
                data = self.snapshot(frame)
            except Exception:
                continue
            if str(data['course_id']) == str(course) and str(data['work_id']) == str(work) and data['questions']:
                found.append((page, frame, data))
        editable = [t for t in found if t[2]['editable']]
        if editable:
            found = editable
        if len(found) != 1:
            code = 'TARGET_NOT_FOUND' if not found else 'AMBIGUOUS_TARGET'
            raise TaskError(f'{code}: course={course}, work={work}; open exactly one matching assignment')
        return found[0]

    def check(self):
        pages, targets = [], []
        for context in self.browser.contexts:
            for page in context.pages:
                url = urlparse(page.url)
                if (url.hostname or '').endswith('.chaoxing.com'):
                    pages.append({'title': page.title(), 'host': url.hostname, 'path': url.path})
        for _, frame in self.candidates():
            try:
                data = self.snapshot(frame)
                if data['questions']:
                    targets.append({k: data[k] for k in ('course_id', 'work_id', 'title', 'editable')})
            except Exception:
                pass
        login = 'logged_in' if any(p['host'] == 'i.chaoxing.com' and p['path'] == '/base' for p in pages) else 'unknown'
        if any(p['host'] == 'passport2.chaoxing.com' and '/login' in p['path'] for p in pages) and login != 'logged_in':
            login = 'login_required'
        return {'browser': 'connected', 'login': login, 'pages': pages, 'assignments': targets}

    def capture_images(self, page, frame, directory, course, work, limit):
        if not re.search(r'/work/(?:dowork|view|review)/?$', urlparse(frame.url).path):
            raise TaskError('UNSUPPORTED_LAYOUT: image preview requires a regular assignment')
        request = {'course_id': str(course), 'work_id': str(work), 'limit': limit}
        targets = frame.evaluate_handle('(arg)=>{const a=' + ADAPTER + ';return a.imageTargets(arg)}', request)
        groups = targets.get_properties().values()
        if not groups:
            return {'status': 'no_images', 'image_questions': []}
        page.bring_to_front()
        cdp = page.context.new_cdp_session(page)
        directory.mkdir(parents=True, exist_ok=True)
        results = []
        for group in groups:
            number = group.get_property('number').json_value()
            record = {'number': number, 'id': group.get_property('id').json_value(),
                      'truncated': group.get_property('truncated').json_value(), 'images': []}
            for order, item in enumerate(group.get_property('images').get_properties().values(), 1):
                part = item.get_property('part').json_value()
                option = item.get_property('option').json_value()
                image = {'part': part, 'option_position': option}
                try:
                    node = item.get_property('node').as_element()
                    available = node.evaluate("""async img => {
                        if (!img.isConnected) return false;
                        img.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});
                        if (!img.complete) await Promise.race([
                            img.decode().catch(()=>{}), new Promise(done => setTimeout(done, 1200))
                        ]);
                        return img.naturalWidth > 0 && img.naturalHeight > 0;
                    }""")
                    box = node.bounding_box() if available else None
                    if not box or min(box['width'], box['height']) < 1:
                        image['error'] = 'IMAGE_NOT_VISIBLE'
                    elif max(box['width'], box['height']) > 2000:
                        image['error'] = 'IMAGE_REGION_TOO_LARGE'
                    else:
                        viewport = cdp.send('Page.getLayoutMetrics')['cssLayoutViewport']
                        clip = {**box, 'x': max(0, box['x'] + viewport['pageX']),
                                'y': max(0, box['y'] + viewport['pageY']), 'scale': 1.25}
                        shot = cdp.send('Page.captureScreenshot', {'format': 'png', 'clip': clip,
                                        'fromSurface': True, 'captureBeyondViewport': True})
                        path = directory / f'question-{number:03}-image-{order:02}.png'
                        path.write_bytes(base64.b64decode(shot['data']))
                        image['file'] = str(path)
                except Exception:
                    image['error'] = 'IMAGE_CAPTURE_FAILED'
                record['images'].append(image)
            results.append(record)
        partial = any(q['truncated'] or any('error' in image for image in q['images']) for q in results)
        return {'status': 'partial_capture' if partial else 'captured', 'image_questions': results}

    def save(self, frame, course, work):
        self.call(frame, 'save', {'course_id': str(course), 'work_id': str(work)})
        try:
            frame.wait_for_function("window.__cxDraftSave && window.__cxDraftSave.status !== 'pending'",
                                    polling=100, timeout=self.timeout)
        except Exception as exc:
            raise TaskError('SAVE_UNCERTAIN: save callback timed out; re-read before retrying') from exc
        result = frame.evaluate('window.__cxDraftSave')
        if result['status'] != 'saved':
            raise TaskError('SAVE_FAILED: ' + result.get('message', 'server rejected'))

    def list_works(self):
        frames = [frame for context in self.browser.contexts for page in context.pages for frame in page.frames
                  if (urlparse(frame.url).hostname or '').endswith('.chaoxing.com')
                  and '/work/getAllWork' in urlparse(frame.url).path]
        if len(frames) != 1:
            raise TaskError('LIST_NOT_FOUND' if not frames else 'AMBIGUOUS_LIST: keep one course list open')
        works = frames[0].evaluate((ROOT / 'list.js').read_text(encoding='utf-8'))
        return {'layout': 'legacy_getAllWork', 'count': len(works), 'works': works}

    def reload(self, page, course, work):
        page.reload(wait_until='domcontentloaded', timeout=self.timeout)
        end = time.monotonic() + self.timeout / 1000
        last = None
        while time.monotonic() < end:
            try:
                result = self.target(course, work)
                ready = result[1].evaluate("!window.UE || Object.values(UE.instants).every(e=>e.isReady)")
                if ready:
                    return result
            except Exception as exc:
                last = exc
            time.sleep(.2)
        raise TaskError('RELOAD_FAILED: assignment not ready') from last


def state_dir(course, work):
    if not str(course).isdigit() or not str(work).isdigit():
        raise TaskError('INVALID_ID: course/work must be numeric')
    return ROOT / 'data' / f'{course}-{work}'


def current_answers(snapshot):
    return {q['id']: {'kind': q['kind'], 'answer': q['answer']} for q in snapshot['questions']
            if q['kind'] in ('text', 'blanks', 'choice')}


def verify_saved(snapshot, expected):
    if not expected:
        raise TaskError('NO_EXPECTED_ANSWERS')
    actual = current_answers(snapshot)
    if set(actual) != set(expected):
        raise TaskError('QUESTION_SET_CHANGED')
    for qid, old in expected.items():
        if qid not in actual or actual[qid]['kind'] != old['kind'] or not equivalent(actual[qid]['answer'], old['answer'], old['kind']):
            raise TaskError(f'RELOAD_MISMATCH: {qid}')
    for q in snapshot['questions']:
        if q['id'] in expected and not equivalent(q['answer'], q.get('form_answer'), q['kind']):
            raise TaskError(f'FIELD_MISMATCH: {q["id"]}')


def redact(message):
    return re.sub(r'(?i)(enc|stuenc|token|access_token|cpi|answerid)=([^\s&"\']+)', r'\1=REDACTED', str(message))[:700]


def browser_command(url, endpoint):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.chaoxing.com')
            or parsed.username or parsed.password):
        raise TaskError('INVALID_URL: only Chaoxing navigation URLs are supported')
    port = validate_endpoint(endpoint)
    candidates = [Path(os.environ['CX_BROWSER'])] if os.environ.get('CX_BROWSER') else [
        Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
        Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft/Edge/Application/msedge.exe',
        Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'Microsoft/Edge/Application/msedge.exe',
    ]
    edge = next((path for path in candidates if path.is_file()), None)
    if edge is None:
        raise TaskError('EDGE_NOT_FOUND: configure an installed browser first')
    return [str(edge), f'--remote-debugging-port={port}', '--remote-debugging-address=127.0.0.1',
            '--user-data-dir=' + str(ROOT / '.browser-profile'), url]


def launch_browser(url, endpoint):
    command = browser_command(url, endpoint)
    profile = ROOT / '.browser-profile'
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {'opened': url, 'profile': str(profile), 'next': 'cx.ps1 check'}


def execute(args):
    if args.command == 'open':
        return launch_browser(args.url, args.endpoint)
    with Browser(args.endpoint, args.timeout * 1000) as browser:
        if args.command == 'check':
            return browser.check()
        if args.command == 'list':
            return browser.list_works()
        directory = state_dir(args.course, args.work)
        page, frame, snapshot = browser.target(args.course, args.work)
        if args.command == 'capture-images':
            return browser.capture_images(page, frame, directory / 'image-preview', args.course, args.work, args.limit)
        if args.command == 'read':
            path = Path(args.out).resolve() if args.out else directory / 'questions.json'
            write_json(path, snapshot)
            template = {'course_id': snapshot['course_id'], 'work_id': snapshot['work_id'], 'answers': {}}
            for q in snapshot['questions']:
                if not snapshot['editable'] or q['kind'] not in ('text', 'blanks', 'choice') or q['manual_only'] or q['has_assets']:
                    continue
                key = {'text': 'text', 'blanks': 'blanks', 'choice': 'choices'}[q['kind']]
                template['answers'][q['id']] = {key: q['answer'], 'fingerprint': q['fingerprint']}
            write_json(directory / 'answers.template.json', template)
            return {**question_summary(snapshot), 'questions': len(snapshot['questions']), 'editable': snapshot['editable'], 'file': str(path),
                    'template': str(directory / 'answers.template.json'),
                    'image_questions': sum(bool(q['images'] or q['needs_vision']) for q in snapshot['questions'])}
        plan = read_json(args.answers) if args.answers else None
        state_path = directory / 'state.json'
        previous = read_json(state_path) if state_path.exists() else {}
        state = {'course_id': args.course, 'work_id': args.work, 'status': 'started'}
        try:
            if args.command in ('fill', 'run'):
                changes = build_changes(snapshot, plan)
                if args.dry_run:
                    return {'dry_run': True, 'planned_changes': [c['id'] for c in changes], 'unchanged': len(plan['answers']) - len(changes)}
                state.update(status='filling', expected=current_answers(snapshot))
                write_json(state_path, state)
                browser.call(frame, 'fill', {'course_id': args.course, 'work_id': args.work, 'changes': changes})
                snapshot = browser.snapshot(frame)
                verify_plan(snapshot, plan)
                state.update(status='filled', changed=len(changes), expected=current_answers(snapshot))
                write_json(state_path, state)
                if args.command == 'fill':
                    return {'status': 'filled', 'changed': len(changes), 'server_saved': False, 'state': str(state_path)}
            elif plan:
                verify_plan(snapshot, plan)
            if args.command in ('save', 'run'):
                if not snapshot['editable']:
                    raise TaskError('READ_ONLY')
                state.update(status='saving', expected=current_answers(snapshot))
                write_json(state_path, state)
                browser.save(frame, args.course, args.work)
                state['status'] = 'saved'
                write_json(state_path, state)
            elif args.command == 'verify':
                if not plan:
                    if not state_path.exists():
                        raise TaskError('NO_CHECKPOINT: supply --answers or run save first')
                    state = read_json(state_path)
                else:
                    state['expected'] = current_answers(snapshot)
            _, frame, snapshot = browser.reload(page, args.course, args.work)
            verify_saved(snapshot, state['expected'])
            if plan:
                verify_plan(snapshot, plan)
            state.update(status='draft_verified', verified_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
                         verified_questions=len(state['expected']))
            write_json(state_path, state)
            return {'status': state['status'], 'verified': state['verified_questions'], 'changed': state.get('changed', 0),
                    'submitted': False, 'state': str(state_path)}
        except Exception as exc:
            if 'expected' not in state and previous.get('expected'):
                state['expected'] = previous['expected']
            state.update(status='failed', error=redact(exc))
            write_json(state_path, state)
            raise


def main():
    parser = argparse.ArgumentParser(description='学习通草稿助手：不提交，不覆盖冲突答案。')
    parser.add_argument('--endpoint', default='http://127.0.0.1:9222')
    parser.add_argument('--timeout', type=int, default=15, help='每步超时秒数')
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('check')
    subs.add_parser('list')
    sub = subs.add_parser('open')
    sub.add_argument('--url', default='https://i.chaoxing.com/base')
    sub = subs.add_parser('capture-images', help='截取最多四道普通作业的题干和选项图片，只读')
    sub.add_argument('--course', required=True)
    sub.add_argument('--work', required=True)
    sub.add_argument('--limit', type=int, choices=range(1, 5), default=4)
    for command in ('read', 'fill', 'save', 'verify', 'run'):
        sub = subs.add_parser(command)
        sub.add_argument('--course', required=True)
        sub.add_argument('--work', required=True)
        if command == 'read':
            sub.add_argument('--out')
        else:
            sub.add_argument('--answers', required=command in ('fill', 'run'))
        if command in ('fill', 'run'):
            sub.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.timeout <= 120:
        parser.error('--timeout must be between 1 and 120')
    finished = threading.Event()
    def deadline():
        # evaluate() has no per-call timeout; a frozen renderer must not hang the CLI forever.
        if not finished.wait(max(30, args.timeout * 6)):
            print(json.dumps({'ok': False, 'error': 'COMMAND_TIMEOUT: inspect the page before retrying'}), flush=True)
            os._exit(124)
    threading.Thread(target=deadline, daemon=True).start()
    try:
        result = execute(args)
        print(json.dumps({'ok': True, **result}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': redact(exc)}, ensure_ascii=False))
        return 1
    finally:
        finished.set()


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
