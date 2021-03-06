import datetime
from typing import Dict

from . import models, rates, categories


def build_simple_question(data: dict, category_provider: categories.Categories) -> models.SimpleQuestion:
    category = category_provider.by_id(int(data['cid']))
    question = models.SimpleQuestion(
        id=int(data['id']),
        title=data['qtext'],
        state=models.QuestionState(data['state']),
        category=category,
        age_seconds=int(data['added']),
        is_leader=bool(int(data['waslead'])),
        poll_type=models.PollType(data['polltype']),
        answer_count=int(data['total_voted'] if data['polltype'] else data['anscnt']),
    )
    return question


def build_question_preview(data: dict, category_provider: categories.Categories) -> models.QuestionPreview:
    base = build_simple_question(data, category_provider)
    user = models.UserPreview(
        id=int(data['usrid']),
        name=data['nick'],
        is_vip=bool(data['vip']),
        kpd=float(data['kpd']),
        about=data['about'],
        avatar=models.Avatar(data['filin']),
        is_expert=bool(data['is_expert']),
    )
    question = models.QuestionPreview(
        **vars(base),
        author=user,
    )
    return question


def build_best_question_preview(data: dict, category_provider: categories.Categories) -> models.BestQuestionPreview:
    base = build_question_preview(data, category_provider)
    question = models.BestQuestionPreview(
        **vars(base),
        can_like=bool(data.get('canmark')),
        like_count=int(data['sum']),
    )
    return question


def build_user_question_preview(data: dict, category_provider: categories.Categories) -> models.UserQuestionPreview:
    base = build_simple_question(data, category_provider)
    question = models.UserQuestionPreview(
        **vars(base),
        is_hidden=bool(data['hidden']),
    )
    return question


def build_small_user_preview(data: dict) -> models.SmallUserPreview:
    if 'brand_cid' in data:
        return build_brand_small_user_preview(data)
    return models.SmallUserPreview(
        id=int(data['id']),
        name=data['nick'],
        avatar=models.Avatar(data['filin']),
        rate=rates.by_name(data['lvl']),
    )


def build_brand_small_user_preview(data: dict) -> models.BrandSmallUserPreview:
    return models.BrandSmallUserPreview(
        id=int(data['id']),
        name=data['nick'],
        avatar=models.Avatar(data['filin']),
        rate=None,
        brand_id=int(data['brand_cid']),
        brand_description=data['brand'],
    )


def build_user(data: dict, user_cache: Dict[int, models.User]) -> models.User:
    user_id = int(data['usrid'])
    if user_id not in user_cache:
        user_cache[user_id] = models.User(
            id=user_id,
            name=data['nick'],
            is_vip=bool(data['vip']),
            kpd=float(data['kpd']),
            about=data['about'],
            avatar=models.Avatar(data['ofilin' if 'ofilin' in data else 'filin']),
            is_expert=bool(data['is_expert']),
            points=int(data['points']) if 'points' in data else None,
            rate=rates.by_user_stats(int(data['points']), float(data['kpd'])) if 'points' in data else None,
        )
        if data.get('brand_url'):
            user_cache[user_id] = models.BrandUser(
                **vars(user_cache[user_id]),
                brand=build_brand(data),
                role=data['role'],
            )
    return user_cache[user_id]


def build_comment_user_preview(data: dict) -> models.CommentUserPreview:
    if data.get('brand_url'):
        return build_brand_comment_user_preview(data)
    return models.CommentUserPreview(
        id=int(data['usrid']),
        name=data['nick'],
        avatar=models.Avatar(data['ofilin']),
        points=int(data['points']),
        rate=rates.by_name(data['lvl']),
    )


def build_brand_comment_user_preview(data: dict) -> models.BrandCommentUserPreview:
    return models.BrandCommentUserPreview(
        id=int(data['usrid']),
        name=data['nick'],
        avatar=models.Avatar(data['ofilin']),
        points=int(data['points']),
        rate=None,
        brand=build_brand(data),
        role=data['role'],
    )


def build_answer(data: dict, user_cache: Dict[int, models.User]) -> models.Answer:
    user = build_user(data, user_cache)
    answer = models.Answer(
        id=int(data['id']),
        author=user,
        text=data['atext'],
        source=data['source'],
        age_seconds=int(data['added']),
        can_like=bool(data.get('canmark')),
        can_thank=bool(data.get('canth')),
        thank_status=models.ThankStatus(data.get('canth_status', 0)),
        like_count=int(data['totalmarks']),
        comment_count=int(data.get('comcnt', 0)),
        vote_count=int(data.get('rating', 0)),
        comments=[build_comment(c, user_cache) for c in data.get('comments', [])],
    )
    return answer


def build_question_addition(data: dict) -> models.QuestionAddition:
    return models.QuestionAddition(
        id=int(data['adnid']),
        age_seconds=int(data['added']),
        text=data['atext'],
    )


def build_poll(data: dict) -> models.Poll:
    options = [
        models.PollOption(
            id=int(o['optid']),
            text=o['text'],
            vote_count=int(o['vote']),
            my_vote=bool(o['ivoted']),
        )
        for o in data['options']
    ]
    return models.Poll(
        type=models.PollType(data['type']),
        vote_count=int(data['total_voted']),
        options=options,
        i_voted=any(o.my_vote for o in options),
    )


def build_comment(data: dict, user_cache: Dict[int, models.User]) -> models.Comment:
    if 'about' in data:
        user = build_user(data, user_cache)
    elif 'nick' in data:
        user = build_comment_user_preview(data)
    else:
        user = None
    return models.Comment(
        id=int(data['cmid']),
        text=data['cmtext'],
        author=user,
        author_id=int(data['usrid']),
        age_seconds=int(data['added']),
        comment_count=int(data['comcnt']),
        comments=[build_comment(c, user_cache) for c in data['comments']],
        parent_id=int(data['parent']),
        reference_id=int(data['refid']),
        number=int(data['num']),
        type=models.CommentType(data['type']),
    )


def build_incomplete_question(data: dict, category_provider: categories.Categories) -> models.IncompleteQuestion:
    category = category_provider.by_id(int(data['cid']))
    user_cache = {}
    user = build_user(data, user_cache)
    answers = {a['id']: build_answer(a, user_cache)
               for a in ([data['best']] if 'best' in data else []) + data['answers']}
    additions = [build_question_addition(a) for a in data['adds']]
    poll = build_poll(data['poll']) if 'poll' in data else None
    comments = [build_comment(c, user_cache) for c in data['comments']] if poll else None
    question = models.IncompleteQuestion(
        id=int(data['qid']),
        category=category,
        author=user,
        can_choose_best_answer=bool(data['acanselbest']),
        age_seconds=int(data['added']),
        like_count=int(data['totalmarks']),
        answer_count=int(data['anscnt']),
        comment_count=int(data['comcnt']),
        can_comment=bool(int(data['cancomment'])),
        can_like=bool(data.get('canmark')),
        can_answer=bool(data['canreply']),
        cannot_answer_reason=data.get('canreplyreason', {}).get('error'),
        title=data['qtext'],
        text=data['qcomment'],
        is_hidden=bool(int(data['hidden'])),
        state=models.QuestionState(data['state']),
        is_leader=bool(int(data['waslead'])),
        is_watching=bool(data['watcher']),
        liked_by=[build_small_user_preview(u) for u in data['marked']],
        answers=list(answers.values()),
        best_answer=answers.get(data['bestanswer']),
        additions=additions,
        poll=poll,
        poll_type=models.PollType(data['polltype']),
        deleted_by_id=int(data['deleted_by']['id']) if 'deleted_by' in data else None,
        comments=comments,
        can_recommend_to_golden=bool(data.get('goldrec')),
        edit_token=data.get('edit_token'),
        brand_answer_status=models.BrandAnswerStatus.answered if data.get('has_brand_answer') else
        models.BrandAnswerStatus.waiting if data.get('waiting_brand_reply') else
        models.BrandAnswerStatus.none,
    )
    return question


def build_question(data: dict, category_provider: categories.Categories) -> models.Question:
    incomplete_question = build_incomplete_question(data, category_provider)
    question = models.Question(
        **vars(incomplete_question),
        best_answer_vote_count=int(data['arating']),
        can_edit=bool(data['can_edit']),
        can_add=not data['noadd'],
        created_at=datetime.datetime.fromtimestamp(int(data['created_at'])),
    )
    return question


def build_user_profile(data: dict, user_id: int, category_provider: categories.Categories
                       ) -> models.UserProfile:
    if 'expert' in data:
        return build_brand_expert_profile(data, user_id, category_provider)
    profile = models.UserProfile(
        id=user_id,
        name=data['snick'],
        points=int(data['spoints']),
        rate=rates.by_name(data['srank']),
        about=data['description'],
        kpd=float(data['skpd']),
        is_expert=bool(data['is_expert']),
        is_vip=bool(data['vip']),
        is_banned=bool(data['banned']),
        is_followed_by_me=bool(data['subscribed']),
        is_hidden=bool(data['hidden']),
        place=int(data['place']),
        answer_count=int(data['sans']),
        best_answer_count=int(data['sbans']),
        deleted_answer_count=int(data['cnt']['deleted_answers']),
        question_count=int(data['sqst']),
        open_question_count=int(data['cnt']['questions_new']),
        voting_question_count=int(data['cnt']['questions_voting']),
        resolved_question_count=int(data['cnt']['questions_resolved']),
        blacklisted_count=int(data['black_cnt']),
        followers_count=int(data['cnt']['followers']),
        following_count=int(data['following']),
        week_points=int(data['weekpoints']),
        avatar=models.Avatar(data['sfilin' if 'sfilin' in data else 'filin']),
    )
    if 'maillogin' in data:
        profile = models.MyUserProfile(
            **vars(profile),
            watching_question_count=int(data['watchcnt']),
            direct_question_count=int(data['cnt']['questions_direct']),
            removed_question_count=int(data['cnt']['questions_removed']),
            banned_until=datetime.datetime.fromtimestamp(data['ban_until']) if 'ban_until' in data else None,
        )
    return profile


def build_brand_expert_profile(data: dict, user_id: int, category_provider: categories.Categories
                               ) -> models.BrandExpertProfile:
    brand = models.BrandBadge(
        urlname=data['company']['page'],
        brand_url=data['company']['url'],
        name=data['company']['name'],
        logo_url=data['company']['logo'],
        background_url=data['company']['bg'],
    )
    profile = models.BrandExpertProfile(
        id=user_id,
        name=data['snick'],
        points=int(data['spoints']),
        rate=rates.by_name(data['srank']),
        about=data['expert']['description'],
        kpd=float(data['skpd']),
        is_expert=bool(data['isExpert']),
        is_vip=bool(data['vip']),
        is_banned=bool(data['banned']),
        is_followed_by_me=not data['canSubscribe'],
        is_hidden=bool(data['hidden']),
        place=None,
        answer_count=int(data['sans']),
        best_answer_count=int(data['sbans']),
        deleted_answer_count=int(data['cnt']['deleted_answers']),
        question_count=int(data['sqst']),
        open_question_count=int(data['cnt']['questions_new']),
        voting_question_count=int(data['cnt']['questions_voting']),
        resolved_question_count=int(data['cnt']['questions_resolved']),
        blacklisted_count=None,
        followers_count=int(data['cnt']['followers']),
        following_count=None,
        week_points=None,
        avatar=models.Avatar(data['sfilin' if 'sfilin' in data else 'filin']),
        categories=[category_provider.by_id(int(c)) for c in data['categories']],
        brand=brand,
        role=data['expert']['role'],
    )
    return profile


def build_limit_set(data: dict) -> models.LimitSet:
    return models.LimitSet(
        questions=int(data['ASK']),
        direct_questions=int(data['DIQ']),
        answers=int(data['AAQ']),
        best_answer_votes=int(data['VBA']),
        poll_votes=int(data['OPV']),
        likes=int(data['QAM']),
        photos=int(data['IMQ']),
        videos=int(data['VIQ']),
        best_question_recommends=int(data['GSR']),
    )


def build_limits(data: dict) -> models.Limits:
    return models.Limits(
        total=build_limit_set(data['total']),
        current=build_limit_set(data['current']),
    )


def build_poll_user_preview(data: dict) -> models.PollUserPreview:
    return models.PollUserPreview(
        id=int(data['id']),
        name=data['nick'],
        avatar=models.Avatar(data['filin']),
        rate=rates.by_name(data['lvl']),
        email=data['email'],
    )


def build_answer_preview(data: dict, category_provider: categories.Categories) -> models.AnswerPreview:
    user = models.MinimalUserPreview(
        id=int(data['qusrid']),
        name=data['qnick'],
        avatar=models.Avatar(data['qfilin']),
    )
    question = models.MinimalQuestionPreview(
        id=int(data['qid']),
        title=data['qtext'],
        state=models.QuestionState(data['qstate']),
        category=category_provider.by_id(int(data['cid'])),
        age_seconds=int(data['qadded']),
        is_leader=bool(int(data['waslead'])),
        poll_type=models.PollType.none,
        answer_count=int(data['anscnt']),
        author=user,
    )
    answer = models.AnswerPreview(
        id=int(data['aid']),
        age_seconds=int(data['aadded']),
        text=data['atext'],
        is_best=bool(data['best']),
        question=question,
    )
    return answer


def build_minimal_question_preview(
        data: dict,
        category_provider: categories.Categories
) -> models.MinimalQuestionPreview:
    user = models.MinimalUserPreview(
        id=int(data['usrid']),
        name=data['qnick'],
        avatar=models.Avatar(data['qfilin']),
    )
    question = models.MinimalQuestionPreview(
        id=int(data['qid']),
        title=data['qtext'],
        state=models.QuestionState(data['state']),
        category=category_provider.by_id(int(data['cid'])),
        age_seconds=int(data['added']),
        is_leader=bool(int(data['waslead'])),
        poll_type=models.PollType(data['polltype']),
        answer_count=int(data['anscnt']),
        author=user,
    )
    return question


def build_user_in_rating(data: dict, rating_type: models.RatingType) -> models.UserInRating:
    user = build_user(data, {})
    return models.UserInRating(
        **vars(user),
        rating_type=rating_type,
        rating_points=int(data['dif' + rating_type.value]),
    )


def build_question_search_result(data: dict, category_provider: categories.Categories) -> models.QuestionSearchResult:
    user = models.MinimalUserPreview(
        id=int(data['author']['id']),
        name=data['author']['nick'],
        avatar=models.Avatar(data['author']['filin']),
    )
    return models.QuestionSearchResult(
        id=int(data['id']),
        title=data['question'],
        text=data.get('qstcomment', ''),
        answer_count=int(data['count']),
        category=category_provider.by_name(data['catname']),
        state=[None, models.QuestionState.resolve, models.QuestionState.vote, models.QuestionState.open][data['state']],
        is_poll=bool(data['is_poll']),
        created_at=datetime.datetime.fromtimestamp(data['time']),
        age_seconds=int(data['time_ago']),
        author=user,
    )


def build_similar_question_search_result(
        data: dict,
        category_provider: categories.Categories
) -> models.SimilarQuestionSearchResult:
    return models.SimilarQuestionSearchResult(
        id=int(data['id']),
        title=data['qtext'],
        category=category_provider.by_id(int(data['cid'])),
    )


def build_follower_preview(data: dict) -> models.FollowerPreview:
    user = build_small_user_preview(data)
    return models.FollowerPreview(
        **vars(user),
        is_followed_by_me=bool(data['fr']),
    )


def build_settings(data: dict) -> models.Settings:
    return models.Settings(
        news='NEW' not in data['pers'],
        sound=data['sets']['sound'] == '0',
        all_mail=data['sets']['mail'] == '0',
        all_web=data['sets']['web'] == '0',
        answer_mail='AQM' not in data['pers'],
        answer_web='AQW' not in data['pers'],
        like_mail='LKM' not in data['pers'],
        like_web='LKW' not in data['pers'],
        comment_mail='COM' not in data['pers'],
        comment_web='COW' not in data['pers'],
        vote_mail='PVM' not in data['pers'],
        vote_web='PVW' not in data['pers'],
    )


def build_brand(data: dict) -> models.Brand:
    return models.Brand(
        urlname=data['brand_url'],
        brand_url=data['url'],
        description=data['brand'],
    )


def build_brand_profile(data: dict) -> models.BrandProfile:
    return models.BrandProfile(
        urlname=data['urlname'],
        brand_url=data['brand_url'],
        name=data['name'],
        logo_url=data['brand_logo'],
        background_url=data['brand_background'],
        id=int(data['id']),
        answer_count=int(data['cnt']['answers']),
        best_answer_count=int(data['cnt']['best_answers']),
        followers_count=int(data['cnt']['followers']),
        open_question_count=int(data['cnt']['questions_new']),
        voting_question_count=int(data['cnt']['questions_voting']),
        resolved_question_count=int(data['cnt']['questions_resolved']),
        description=data['brand_persontext'],
        is_followed_by_me=bool(data.get('subscribed')),
    )
