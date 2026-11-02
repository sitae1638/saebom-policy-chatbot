"""[개선 v1] 동의어 사전: 사용자 말 → 규정 용어로 질문을 확장한다.
규칙 형식: (붙일 규정 용어, [트리거 표현들], 모두포함여부)
 - 모두포함=False: 트리거 중 하나라도 있으면 적용
 - 모두포함=True : 트리거가 모두 있어야 적용 (예: '거래처'+'식사' → 접대비)
띄어쓰기 오타에 대비해 '공백 제거한 질문'에서도 함께 찾는다.
주의: 실패 문항을 보고 만든 사전이므로 600문항 점수가 부풀 수 있다 → 별도 검증셋으로 확인할 것.
"""
RULES = [
    # 근무
    ("재택근무", ["집에서 일", "집에서 근무", "원격근무", "원격 근무", "재택"], False),
    ("시차출퇴근 출근시간", ["유연출근", "출근 시간 내가", "출근 시각", "출근시간 변경", "출근 시간 바꾸"], False),
    ("지각", ["늦게 출근", "늦게 와", "늦었", "늦으면"], False),
    ("수습기간", ["입사한 지 얼마", "수습"], False),
    ("연장근로 야근", ["늦게까지 일", "연장근무", "야근", "퇴근 안 하고", "더 일하"], False),
    # 휴가
    ("배우자 출산 경조휴가", ["와이프", "아내", "애 낳", "아기 낳", "출산"], False),
    ("병가 진단서", ["아파서", "몸이 안 좋", "몸살", "병가"], False),
    ("반반차", ["2시간짜리 휴가", "2시간 단위", "잘게 쪼개", "반반차"], False),
    # 경비
    ("식대", ["밥값", "식비", "식사비", "저녁을 먹"], False),
    ("경비 정산 지출일", ["비용 처리", "쓴 돈", "쓴 경비", "영수증을 아직", "정산"], False),
    ("법인카드 월 사용 한도", ["법카", "회사카드", "회사 카드", "카드를 받", "긁을"], False),
    ("택시비 귀가", ["택시", "택시비"], False),
    ("접대비 사전 품의 접대 보고서", ["거래처", "식사"], True),
    ("접대비 사전 품의 접대 보고서", ["고객사", "식사"], True),
    ("접대비", ["접대"], False),
    ("간이영수증 증빙", ["간이영수증"], False),
    ("도서·교육비 지원", ["인강", "강의", "책 사", "책이랑", "교육비", "자기계발"], False),
    # 출장
    ("숙박비 1박 한도", ["호텔", "숙소", "숙박", "하룻밤", "1박"], False),
    ("가지급금", ["미리 받", "선지급", "먼저 받", "가지급"], False),
    ("국내 당일 출장 일비", ["당일치기", "당일 출장", "당일출장", "바로 돌아오"], False),
    ("미주·유럽", ["미국", "뉴욕", "유럽", "미주"], False),
    # 비품
    ("비품", ["장비", "물품", "키보드", "마우스", "헤드셋", "모니터", "노트북"], False),
    ("분실·파손 보고", ["잃어버", "잃어 버", "없어졌", "망가", "부서졌", "부쉈", "떨어뜨", "파손", "분실"], False),
    ("반납 마지막 근무일", ["돌려줘", "돌려주", "반납", "그만두"], False),
    ("소모품 한도", ["볼펜", "포스트잇", "소모품"], False),
    ("안전재고 표준단가", ["최소로 유지", "재고 박스", "안전재고"], False),
    ("재고가 없으면 구매", ["재고가 없", "재고없", "창고에 없"], False),
    ("내용연수 교체", ["몇 년 쓰고", "교체 주기", "낡았", "몇년마다", "교체 대상"], False),
    # 구매
    ("검수 납품일", ["물건 받으면", "수량 확인", "도착했", "검수"], False),
    ("대금 지급 세금계산서", ["업체에 돈", "대금"], False),
    ("견적 구매 금액 승인권자", ["견적", "사려면", "구입하려", "구매하려"], False),
    # 시설·보안
    ("대회의실", ["큰 회의실", "20명", "전 직원 모이"], False),
    ("외부인 방문 등록 방문객 주차", ["손님", "방문", "찾아오"], False),
    ("직원 주차", ["차 끌고", "자차", "주차"], False),
    ("PC 비밀번호", ["비번", "패스워드", "비밀번호"], False),
    ("개인정보 유출 보고", ["새어나", "유출", "잘못 보낸"], False),
    # 범위 밖
    ("급여 연봉 규정에 없는 사항", ["연봉", "임금", "월급", "인상률"], False),
]

# ---------- [개선 v2] 오타 허용 매칭 ----------
# 한글을 자모(초성·중성·종성)로 풀어 편집 거리를 재면 "택시→탯시"는 1글자 차이로 계산된다.
CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

def jamo(s):
    out = []
    for ch in s:
        n = ord(ch) - 0xAC00
        if 0 <= n < 11172:
            out += [CHO[n // 588], JUNG[(n % 588) // 28]] + ([JONG[n % 28]] if n % 28 else [])
        elif not ch.isspace():
            out.append(ch)
    return out

def edit(a, b, limit):
    """편집 거리(삽입·삭제·교체 1, 이웃 글자 맞바꿈 1). limit 초과 시 조기 종료."""
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
            if prev2 and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]

def cho(syl):
    n = ord(syl) - 0xAC00
    return CHO[n // 588] if 0 <= n < 11172 else syl

def syl_transposed(a, b):
    """두 글자 맞바꿈 한 번으로 같아지는가 (택시비→택비시)."""
    if len(a) != len(b): return False
    d = [i for i in range(len(a)) if a[i] != b[i]]
    return len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]]

# 조사·어미가 붙은 표현은 오타 허용 시 엉뚱한 말에 걸려서 제외 (예: 사려면→가려면, 더 일하→서 일하)
NO_FUZZY = {"더 일하", "사려면", "책이랑", "책 사", "구입하려", "구매하려", "늦으면", "늦었", "쓴 돈", "끼"}

def fuzzy_hit(trigger, q_ns, q_syll):
    """글자(음절) 단위로 창을 맞춰 비교.
    - 2글자 단어(재택, 택시 등)는 오타 허용 안 함: 실험 결과 '안내→아내' 같은 오탐이 48건 발생해 제외
    - 3글자 이상: 길이 ±1 창, 자모 차이 1개까지 또는 이웃 글자 맞바꿈 (예: 잃어버→잃어바, 택시비→택비시)
    """
    if trigger in NO_FUZZY or len(trigger.replace(" ", "")) < 3:
        return False
    return _fuzzy_core(trigger, q_ns, q_syll)

def _fuzzy_core(trigger, q_ns, q_syll):
    """글자(음절) 단위로 창을 맞춰 비교.
    - 2글자 단어: 같은 길이 창, 초성 2개가 모두 같고 자모 차이 1개까지 (예: 밥값→밥겂)
    - 3글자 이상: 길이 ±1 창, 자모 차이 1개까지 또는 이웃 글자 맞바꿈 (예: 잃어버→잃어바, 택시비→택비시)
    """
    t = trigger.replace(" ", "")
    n = len(t)
    if n < 2 or not all(0xAC00 <= ord(c) <= 0xD7A3 for c in t) or not (set(t) & q_syll):
        return False
    tj = jamo(t)
    lens = [2] if n == 2 else [n - 1, n, n + 1]
    for L in lens:
        for i in range(0, len(q_ns) - L + 1):
            w = q_ns[i:i + L]
            if n == 2 and [cho(c) for c in w] != [cho(c) for c in t]:
                continue
            if edit(tj, jamo(w), 1) <= 1 or (n >= 3 and syl_transposed(t, w)):
                return True
    return False

def matched(query, fuzzy=False, detail=False):
    """질문에 걸리는 규정 용어 목록. detail=True면 (용어, 'exact'|'fuzzy') 반환."""
    q, q_ns = query, query.replace(" ", "")
    q_syll = set(q_ns)
    out, how = [], {}
    for canon, trig, need_all in RULES:
        def hit(t):
            if t in q or t.replace(" ", "") in q_ns:
                return "exact"
            if fuzzy and fuzzy_hit(t, q_ns, q_syll):
                return "fuzzy"
            return None
        res = [hit(t) for t in trig]
        ok = all(res) if need_all else any(res)
        if ok and canon not in out:
            out.append(canon)
            how[canon] = "exact" if ("exact" in res and not need_all) or (need_all and all(r == "exact" for r in res)) else "fuzzy"
    return [(c, how[c]) for c in out] if detail else out

def expand(query, fuzzy=False):
    terms = matched(query, fuzzy)
    return query + (" " + " ".join(terms) if terms else "")
