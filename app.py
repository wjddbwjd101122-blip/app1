'''엄마도 사람이야! | streamlit run app.py
Python 3.10+. SQLite demo storage: Streamlit Cloud local disk is NOT durable.
Optional Streamlit secrets: FAMILY_PIN, MOM_PIN, DATABASE_PATH, PUBLIC_APP_URL.
Set strong, different PINs before sharing. PINs are a lightweight family gate,
not a production authentication system. Separate deployments have separate data.
'''
import os
import io
import json
import hmac
import hashlib
import secrets
import calendar
import sqlite3
from datetime import date, datetime, timedelta
import pandas as pd
import qrcode
import streamlit as st

st.set_page_config(page_title='엄마도 사람이야!', page_icon='🌷', layout='centered', initial_sidebar_state='collapsed')
def config(key, default=''):
    try:
        return str(st.secrets.get(key, os.environ.get(key, default)))
    except Exception:
        return os.environ.get(key, default)
DB = config('DATABASE_PATH', 'family_diary.db')
def connect():
    con=sqlite3.connect(DB, timeout=20)
    con.row_factory=sqlite3.Row
    return con
with connect() as c:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS checks(day TEXT NOT NULL,child INTEGER NOT NULL,quest TEXT NOT NULL,approved INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(day,child));
    CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,title TEXT,day TEXT,budget INTEGER,memo TEXT,done INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS payments(month TEXT,child INTEGER,half INTEGER,amount INTEGER,paid_at TEXT,PRIMARY KEY(month,child,half));
    ''')
def setting(k, default):
    with connect() as c:
        r=c.execute('SELECT v FROM settings WHERE k=?',(k,)).fetchone()
    return json.loads(r['v']) if r else default
def save(k,v):
    with connect() as c: c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(k,json.dumps(v,ensure_ascii=False)))
def rows(sql,args=()):
    with connect() as c: return c.execute(sql,args).fetchall()
def execute(sql,args=()):
    with connect() as c: c.execute(sql,args)
def streak_ok(child, start, end):
    if end<start:return False
    r=rows('SELECT COUNT(*) n FROM checks WHERE child=? AND day BETWEEN ? AND ? AND approved=1',(child,start.isoformat(),end.isoformat()))[0]['n']
    return r==(end-start).days+1

def eligible(child, month, half, today):
    first=date.fromisoformat(month+'-01')
    last=first.replace(day=calendar.monthrange(first.year, first.month)[1])
    end=first.replace(day=15) if half==1 else last
    return today>=end and streak_ok(child, first, end)

st.markdown('''<style>
.block-container{max-width:780px;padding-top:2.5rem;padding-bottom:1rem}
header[data-testid="stHeader"]{height:0.6rem}
.stApp{background:linear-gradient(135deg,#fffaf6,#fff0f4)}
h1{font-size:1.65rem!important;color:#824858}
.stButton>button{border-radius:14px}
[data-testid="stMetricValue"]{font-size:1.3rem}
</style>''',unsafe_allow_html=True)
st.title('🌷 엄마도 사람이야!')
st.caption('엄마의 쉬는 시간은 늘리고, 우리 가족의 추억은 더하고')
def pin_digest(pin, salt):
    return hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), bytes.fromhex(salt), 200000).hex()

def verify_pin(pin, role):
    configured=config('FAMILY_PIN' if role=='family' else 'MOM_PIN')
    if configured:
        return hmac.compare_digest(pin.encode('utf-8'), configured.encode('utf-8'))
    record=setting('access_'+role, None)
    return bool(record and hmac.compare_digest(pin_digest(pin,record['salt']),record['digest']))

missing=[role for role,key in [('family','FAMILY_PIN'),('mom','MOM_PIN')]
         if not config(key) and not setting('access_'+role,None)]
if missing:
    st.subheader('🏡 우리 가족 첫 설정')
    st.caption('앱을 처음 연 가족이 접속 코드를 등록해 주세요. 외부에 주소를 공유하기 전에 설정하세요.')
    with st.form('initial_setup'):
        new_family=st.text_input('가족 접속 코드 · 6자 이상',type='password')
        new_mom=st.text_input('엄마 승인 코드 · 가족 코드와 다르게',type='password')
        confirm=st.text_input('엄마 승인 코드 다시 입력',type='password')
        submitted=st.form_submit_button('등록하고 시작하기',use_container_width=True)
    if submitted:
        if len(new_family)<6 or len(new_mom)<6:
            st.error('두 코드 모두 6자 이상으로 입력해 주세요.')
        elif new_family==new_mom:
            st.error('가족 코드와 엄마 코드는 다르게 정해 주세요.')
        elif new_mom!=confirm:
            st.error('엄마 승인 코드가 서로 다릅니다.')
        elif ('family' not in missing and not verify_pin(new_family,'family')) or ('mom' not in missing and not verify_pin(new_mom,'mom')):
            st.error('이미 설정된 코드는 기존 코드와 동일하게 입력해 주세요.')
        else:
            with connect() as c:
                for role,pin in [('family',new_family),('mom',new_mom)]:
                    if role in missing:
                        salt=secrets.token_hex(16)
                        value=json.dumps({'salt':salt,'digest':pin_digest(pin,salt)})
                        c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',('access_'+role,value))
            st.rerun()
    st.caption('코드는 해시 형태로 저장합니다. 클라우드의 내부 저장소가 초기화되면 기록과 접속 코드도 초기화될 수 있습니다.')
    st.stop()
if not st.session_state.get('family_login'):
    with st.form('login'):
        pin=st.text_input('가족 접속 코드',type='password')
        submit=st.form_submit_button('우리 집 들어가기',use_container_width=True)
    if submit:
        if verify_pin(pin,'family'):
            st.session_state.family_login=True; st.rerun()
        else: st.error('접속 코드를 확인해 주세요.')
    st.stop()

names=setting('names',['첫째','둘째','셋째'])
quests=setting('quests',['내 자리 정리하기','내 자리 정리하기','내 자리 정리하기'])
allowance=setting('allowance',[30000,30000,30000])
chores=setting('chores',['설거지 돕기','빨래 정리','분리수거'])
anchor=date.fromisoformat(setting('anchor','2026-01-01'))
today=date.today(); month=today.strftime('%Y-%m'); first=today.replace(day=1)
last=today.replace(day=calendar.monthrange(today.year,today.month)[1])
who=st.selectbox('누가 들어왔나요?',['엄마']+names,label_visibility='collapsed')
is_mom=who=='엄마'
if is_mom and not st.session_state.get('mom_login'):
    with st.form('mom_login'):
        pin=st.text_input('엄마 승인 코드',type='password')
        login=st.form_submit_button('엄마 모드 열기')
    if login:
        if verify_pin(pin,'mom'):st.session_state.mom_login=True;st.rerun()
        else:st.error('엄마 승인 코드가 맞지 않습니다.')
    st.stop()
if is_mom:
    if st.button('엄마 모드 잠그기'):st.session_state.pop('mom_login',None);st.rerun()
section=st.segmented_control('메뉴',['오늘','추억 계획','용돈','설정'],default='오늘',label_visibility='collapsed')
# Same page, content swaps to keep the initial mobile view compact. No content is clipped.
if section=='오늘':
    st.subheader(f'☀️ {today:%m월 %d일} · 오늘의 팀워크')
    offset=(today-anchor).days%3
    assignment={i:chores[(i-offset)%3] for i in range(3)}
    st.caption(' · '.join(f'{names[i]}: {assignment[i]}' for i in range(3)))
    if is_mom:
        for i,name in enumerate(names):
            r=rows('SELECT * FROM checks WHERE day=? AND child=?',(today.isoformat(),i))
            a,b=st.columns([3,1])
            a.write(f'**{name}** · {r[0]["quest"] if r else quests[i]}')
            if not r: b.caption('아직 미제출')
            elif r[0]['approved']:
                b.caption('✅ 승인')
            elif b.button('승인',key=f'approve{i}'):
                execute('UPDATE checks SET approved=1 WHERE day=? AND child=?',(today.isoformat(),i));st.rerun()
        st.caption('당일 제출한 개인 퀘스트를 엄마가 승인하면 개근에 반영됩니다. 집안일 순번은 별도 안내이며, 용돈 조건은 개인 퀘스트입니다.')
    else:
        i=names.index(who)
        st.info(f'오늘의 도움: {assignment[i]}  |  내 퀘스트: {quests[i]}')
        r=rows('SELECT * FROM checks WHERE day=? AND child=?',(today.isoformat(),i))
        if not r:
            if st.button('🙌 오늘 퀘스트 완료! 엄마에게 확인 요청',use_container_width=True):
                execute('INSERT OR IGNORE INTO checks(day,child,quest) VALUES (?,?,?)',(today.isoformat(),i,quests[i]));st.rerun()
        else:st.success('엄마 확인 완료 ✅' if r[0]['approved'] else '엄마 확인을 기다리고 있어요 ⏳')
        st.caption('하루 한 번, 오늘 날짜로만 제출할 수 있어요. 하루라도 빠지면 이달 개근을 달성할 수 없어요.')
    with st.expander('이번 주 집안일 순번'):
        table=[]
        for n in range(7):
            d=today+timedelta(days=n);o=(d-anchor).days%3
            table.append({'날짜':d.strftime('%m/%d'),**{names[i]:chores[(i-o)%3] for i in range(3)}})
        st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
    if is_mom:
        pending=rows('SELECT * FROM checks WHERE approved=0 AND day<? ORDER BY day DESC',(today.isoformat(),))
        if pending:
            with st.expander(f'이전 날짜 승인 대기 {len(pending)}건'):
                for r in pending:
                    a,b=st.columns([3,1]);a.caption(f'{r["day"]} · {names[r["child"]]} · {r["quest"]}')
                    if b.button('승인',key=f'old{r["day"]}{r["child"]}'):
                        execute('UPDATE checks SET approved=1 WHERE day=? AND child=?',(r['day'],r['child']));st.rerun()
elif section=='추억 계획':
    st.subheader('🎬 엄마와 함께하는 시간')
    plans=rows('SELECT * FROM plans ORDER BY done,day,id')
    active=[r for r in plans if not r['done']]
    if active:
        r=active[0];st.info(f'{r["kind"]} · {r["title"]} | {r["day"]} | {r["budget"]:,}원')
    else:st.caption('여행이 부담스럽다면 영화 한 편부터 어때요?')
    with st.expander('여행 / 영화 계획 추가',expanded=not bool(active)):
        with st.form('plan',clear_on_submit=True):
            a,b=st.columns(2);kind=a.selectbox('활동',['여행','영화']);d=b.date_input('날짜',min_value=today)
            title=st.text_input('장소 또는 영화 제목',max_chars=70)
            a,b=st.columns(2);budget=a.number_input('총 예상 비용(원)',min_value=0,step=1000);memo=b.text_input('역할·준비물',max_chars=100)
            submit=st.form_submit_button('계획 추가',use_container_width=True)
        if submit:
            if not title.strip():st.error('장소나 영화 제목을 적어주세요.')
            else:execute('INSERT INTO plans(kind,title,day,budget,memo) VALUES (?,?,?,?,?)',(kind,title.strip(),str(d),int(budget),memo));st.rerun()
    with st.expander(f'전체 계획 {len(plans)}개'):
        for r in plans:
            st.write(f'{"✅" if r["done"] else "📌"} {r["day"]} · {r["title"]} · {r["budget"]:,}원')
            st.caption(r['memo'])
            if is_mom and not r['done'] and st.button('다녀왔어요',key=f'done{r["id"]}'):
                execute('UPDATE plans SET done=1 WHERE id=?',(r['id'],));st.rerun()
elif section=='용돈':
    st.subheader('🪙 개근으로 완성하는 용돈')
    st.caption('1~15일 개근 → 절반 선지급 / 1일~말일 개근 → 나머지 지급. 후반 실패 시 선지급분은 회수하지 않습니다. 월 총액 보장 조건은 한 달 개근입니다.')
    selected=st.date_input('정산할 달',value=today).replace(day=1)
    m=selected.strftime('%Y-%m');end=selected.replace(day=calendar.monthrange(selected.year,selected.month)[1])
    ids=range(3) if is_mom else [names.index(who)]
    for i in ids:
        approved=rows('SELECT COUNT(*) n FROM checks WHERE child=? AND approved=1 AND day BETWEEN ? AND ?',(i,str(selected),str(end)))[0]['n']
        st.write(f'**{names[i]}** · 승인 {approved}/{end.day}일 · 월 {allowance[i]:,}원')
        st.progress(min(approved/end.day,1.0))
        a,b=st.columns(2)
        for half,col in [(1,a),(2,b)]:
            amount=allowance[i]//2 if half==1 else allowance[i]-allowance[i]//2
            paid=rows('SELECT * FROM payments WHERE month=? AND child=? AND half=?',(m,i,half))
            ok=eligible(i,m,half,today)
            col.caption(f'{"15일 선지급" if half==1 else "월말 잔금"} · {amount:,}원')
            if paid:col.success(f'지급 기록 {paid[0]["amount"]:,}원')
            elif is_mom:
                if col.button('지급 완료 기록',key=f'pay{i}{half}',disabled=not ok):
                    # Recheck eligibility before inserting; unique key prevents duplicates.
                    if eligible(i,m,half,today):
                        execute('INSERT OR IGNORE INTO payments VALUES (?,?,?,?,?)',(m,i,half,amount,datetime.now().isoformat(timespec='seconds')))
                    st.rerun()
            else:col.caption('지급 가능' if ok else '조건 충족 대기')
    st.caption('실제 송금 기능이 아니라 엄마가 지급 사실을 기록하는 장부입니다. 누락된 제출일을 과거로 소급해 만들 수는 없습니다.')
    with st.expander('이번 달 달력 기록'):
        data=rows('SELECT day,child,quest,approved FROM checks WHERE day BETWEEN ? AND ? ORDER BY day,child',(str(selected),str(end)))
        visible=[dict(r) for r in data if is_mom or r['child']==names.index(who)]
        if visible:
            df=pd.DataFrame(visible);df['child']=df['child'].map(dict(enumerate(names)));df['approved']=df['approved'].map({0:'대기',1:'승인'})
            st.dataframe(df.rename(columns={'day':'날짜','child':'자녀','quest':'퀘스트','approved':'상태'}),hide_index=True,use_container_width=True)
        else:st.caption('아직 기록이 없습니다.')
elif section=='설정':
    st.subheader('⚙️ 우리 집 약속')
    if is_mom:
        with st.expander('자녀 · 퀘스트 · 용돈 · 집안일 설정'):
            with st.form('settings'):
                nn=[];qq=[];aa=[];cc=[]
                for i in range(3):
                    st.caption(f'자녀 {i+1}')
                    a,b=st.columns(2);nn.append(a.text_input('이름',names[i],key=f'n{i}',max_chars=15));aa.append(b.number_input('월 용돈',min_value=0,value=int(allowance[i]),step=1000,key=f'a{i}'))
                    qq.append(st.text_input('매일 개인 퀘스트',quests[i],key=f'q{i}',max_chars=70))
                    cc.append(st.text_input(f'순환 집안일 {i+1}',chores[i],key=f'c{i}',max_chars=40))
                ad=st.date_input('순번 기준일',value=anchor)
                submit=st.form_submit_button('설정 저장')
            if submit:
                nn=[n.strip() for n in nn]
                if any(not v.strip() for v in nn+qq+cc) or len(set(nn))!=3 or '엄마' in nn:st.error('빈칸 없이 입력하고, 자녀 이름은 서로 다르게 해주세요. “엄마”는 자녀 이름으로 사용할 수 없습니다.')
                else:
                    for k,v in [('names',nn),('quests',qq),('allowance',[int(x) for x in aa]),('chores',cc),('anchor',str(ad))]:save(k,v)
                    st.rerun()
            st.caption('자녀 순서가 기록의 기준입니다. 기존 자녀를 바꾸면 기록도 이어집니다. 용돈 수정은 미지급 금액에 즉시 반영되고, 제출한 퀘스트 내용은 그대로 남습니다.')
        with st.expander('데이터 백업'):
            backup={t:[dict(r) for r in rows('SELECT * FROM '+t) if t!='settings' or not r['k'].startswith('access_')] for t in ['settings','checks','plans','payments']}
            st.download_button('JSON 백업 다운로드',json.dumps(backup,ensure_ascii=False,indent=2),file_name=f'family_backup_{today}.json',mime='application/json')
            st.caption('보관용 백업이며 이 버전에는 자동 복원 기능이 없습니다. 개인정보가 포함되므로 안전하게 보관하세요.')
    with st.expander('QR로 가족 초대'):
        url=st.text_input('배포한 앱의 HTTPS 주소',value=config('PUBLIC_APP_URL'),placeholder='https://your-app.streamlit.app')
        if url:
            if not url.startswith('https://'):st.error('실제 배포한 HTTPS 주소를 입력해 주세요.')
            else:
                image=qrcode.make(url);buf=io.BytesIO();image.save(buf,format='PNG')
                st.image(buf.getvalue(),width=170)
                st.download_button('QR 이미지 받기',buf.getvalue(),'family_qr.png','image/png')
                st.caption('QR은 접속 링크입니다. 접속 코드는 QR에 넣지 말고 가족에게 따로 전달하세요.')
    st.warning('체험용 로컬 저장: Streamlit Cloud에서는 재시작·재배포 등으로 데이터가 사라질 수 있습니다. PIN 방식은 간단한 가족용 접근 제한이며, 자녀별 본인 인증은 하지 않습니다. 같은 가족 코드를 아는 사람은 다른 자녀를 선택할 수 있습니다.')
    st.caption('스마트폰 세로 화면에 맞춘 짧은 기본 화면입니다. 작은 화면·큰 글꼴·키보드·펼친 설정에서는 스크롤이 필요합니다. 다른 기기의 변경 사항은 새로고침 후 표시됩니다. 날짜는 실행 서버 기준입니다.')
    if st.button('가족 로그아웃'):
        st.session_state.clear();st.rerun()
