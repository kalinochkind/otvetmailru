import itertools
import json
import re
import time
from typing import Optional, Dict, Callable, Union, List, Iterator

import requests

from . import error, models, factories, categories, utils


MethodArgs = Dict[str, Union[str, int]]
StateInput = Union[str, models.QuestionState, None]
CategoryInput = Union[str, models.Category, None]
UserInput = Union[int, models.BaseUser, None]
OptionInput = Union[int, models.PollOption]
QuestionInput = Union[int, models.BaseQuestion]
AnswerInput = Union[int, models.BaseAnswer]
CommentInput = Union[int, models.Comment]


def normalize_state(state: StateInput) -> Optional[models.QuestionState]:
    if state is None:
        return None
    if not isinstance(state, models.QuestionState):
        state = models.QuestionState(state)
    return state


def normalize_option(option: OptionInput) -> int:
    if isinstance(option, models.PollOption):
        return option.id
    return option


def normalize_question(question: QuestionInput) -> int:
    if isinstance(question, models.BaseQuestion):
        return question.id
    return question


def normalize_answer(answer: AnswerInput) -> int:
    if isinstance(answer, models.BaseAnswer):
        return answer.id
    return answer


def normalize_comment(comment: CommentInput) -> int:
    if isinstance(comment, models.Comment):
        return comment.id
    return comment


def extract_categories_json(page: str) -> List[dict]:
    string = re.search(r'var CATEGORIES = (\[.*)$', page, re.MULTILINE).group(1)
    return utils.read_json_prefix(string)


def iterate_pages(get_page: Callable[[int], list], step: int) -> Iterator[list]:
    for p in itertools.count(0, step):
        data = get_page(p)
        if data:
            yield data
        if len(data) < step:
            return


class OtvetClient:
    """
    otvet.mail.ru API client

    :ivar user_id: id of the authenticated user, or None
    """
    _headers = {'Referer': 'https://otvet.mail.ru/'}

    def __init__(self, *, session: requests.Session = None, auth_info: str = None,
                 auto_renew_token: bool = True, api_retry_attempts: int = 3):
        """
        :param session: requests session that will be used for http requests
        :param auth_info: authentication string previously returned by auth_info property, to reuse old authentication
        :param auto_renew_token: renew the authentication token automatically when it expires
        :param api_retry_attempts: how many times to retry http requests on connection errors
        """
        self._session = session or requests.Session()
        self._auth_dict: Dict[str, str] = {}
        self.user_id: Optional[int] = None
        self._is_adult: Optional[bool] = None
        self._categories: Optional[categories.Categories] = None
        self._auto_renew_token: bool = auto_renew_token
        self._api_retry_attempts = api_retry_attempts
        if auth_info:
            self._load_auth_info(auth_info)

    def _load_main_page(self) -> None:
        main_page = self._session.get('https://otvet.mail.ru/?login=1').text
        if not self._categories:
            self._categories = categories.Categories(extract_categories_json(main_page))
        if 'ot' in self._session.cookies:
            token = self._session.cookies['ot']
            salt = re.search(r'"salt" : "([a-zA-Z0-9]+)"', main_page).group(1)
            self.user_id = int(re.search(r'"id" : "([0-9]+)"', main_page).group(1))
            self._auth_dict = {'token': token, 'salt': salt}
            self._is_adult = re.search(r'"is_adult" : (true|false),', main_page).group(1) == 'true'
        else:
            self.user_id = None
            self._auth_dict = {}
            self._is_adult = None

    def _load_auth_info(self, auth_info) -> None:
        data = json.loads(auth_info)
        self._auth_dict = data['dict']
        self.user_id = data['user_id']
        self._session.cookies.set('Mpop', data['cookie'], domain='.mail.ru')

    def _call_api(self, method: str, params: MethodArgs, direct: bool = False) -> dict:
        real_params = {**params, **self._auth_dict}
        if direct:
            result = self._session.get(method, params=real_params, headers=self._headers)
        else:
            real_params['__urlp'] = method
            result = self._session.post('https://otvet.mail.ru/api/', real_params, headers=self._headers)
        return result.json()

    def _check_response(self, response: dict, allow_retry: bool) -> bool:
        if int(response.get('status', 200)) < 400:
            return False
        if allow_retry:
            if response.get('error') == 'invalid_token' and self._auto_renew_token:
                self._load_main_page()
                return True
        raise error.OtvetAPIError(response)

    def _call_checked(self, method: str, params: MethodArgs, direct: bool = False) -> dict:
        for _ in range(self._api_retry_attempts):
            try:
                result = self._call_api(method, params, direct)
            except requests.exceptions.ConnectionError:
                time.sleep(1)
                continue
            else:
                break
        else:
            result = self._call_api(method, params, direct)
        if self._check_response(result, True):
            result = self._call_api(method, params, direct)
            self._check_response(result, False)
        return result

    def _normalize_user(self, user: UserInput) -> int:
        if isinstance(user, models.BaseUser):
            return user.id
        if user is not None:
            return user
        if self.user_id is not None:
            return self.user_id
        raise error.OtvetArgumentError('Either authenicate the client or provide a user')

    def _ensure_authenticated(self) -> None:
        if self.user_id is None:
            raise error.OtvetArgumentError('Authentication is required to call this method')

    def _normalize_category(self, category: CategoryInput) -> Optional[str]:
        if not category:
            return None
        if isinstance(category, str):
            c = self.categories.by_urlname(category) or self.categories.by_name(category)
            if not c:
                raise error.OtvetArgumentError(f'No such category: {category}')
            return c.urlname
        return category.urlname


    @property
    def is_adult(self) -> Optional[bool]:
        """Is the authenticated user adult. Some categories may be unavailable for non-adult users.
        Use set_is_adult_flag method to set it to true."""
        if self._is_adult is not None or not self.user_id:
            return self._is_adult
        self._load_main_page()
        return self._is_adult

    @property
    def categories(self) -> categories.Categories:
        """Container with all categories, can be queried or iterated."""
        if not self._categories:
            self._load_main_page()
        return self._categories

    @property
    def auth_info(self) -> str:
        """Auth info string that can be saved and reused later."""
        return json.dumps({
            'dict': self._auth_dict,
            'user_id': self.user_id,
            'cookie': self._session.cookies.get('Mpop'),
        })

    def authenticate(self, login: str, password: str) -> None:
        """Authenticate the client with mail.ru username and password."""
        if '@' not in login:
            login += '@mail.ru'
        self._session.post('https://auth.mail.ru/cgi-bin/auth',
                           {'Login': login, 'Username': login, 'Password': password})
        self._load_main_page()
        if self.user_id is None:
            raise error.OtvetAuthError(login)


    def get_questions_page(self, state: StateInput = 'A', category: CategoryInput = None,
                           step: Optional[int] = 20, offset: int = None, lastid: int = None,
                           category_exclude: str = '', only_leaders: bool = False) -> List[models.QuestionPreview]:
        """
        A page of questions.
        :param state: state of the questions (open, voting, resolved), open by default
        :param category: category of the questions (all by default)
        :param step: number of questions
        :param offset: offset of the first question
        :param lastid: the question that should be considered first (for stable pagination)
        :param only_leaders: return only leader questions
        :return: list of questions
        """
        state = normalize_state(state)
        category = self._normalize_category(category)
        params: MethodArgs = {'state': state.value} if state is not None else {}
        if category_exclude or (state is models.QuestionState.open and category is None and not only_leaders):
            params['category_exclude'] = category_exclude
        utils.update_not_none(params, {'cat': category, 'p': offset, 'lastid': lastid, 'n': step})
        data = self._call_checked('/v2/leadqst' if only_leaders else '/v2/questlist', params)
        return [factories.build_question_preview(q, self.categories) for q in data['qst']]

    def get_best_questions_page(self, category: CategoryInput = None, step: int = 20,
                                offset: int = None, lastid: int = None) -> List[models.BestQuestionPreview]:
        """
        A page of best questions.
        :param category: category of the questions (all by default)
        :param step: number of questions
        :param offset: offset of the first question
        :param lastid: the question that should be considered first (for stable pagination)
        :return: list of best questions
        """
        category = self._normalize_category(category)
        params = {'state': 'B', 'n': step}
        utils.update_not_none(params, {'cat': category, 'p': offset, 'lastid': lastid})
        data = self._call_checked('/v2/qstrating', params)
        return [factories.build_best_question_preview(q, self.categories) for q in data['qst']]

    def get_user_questions_page(self, user: UserInput = None, state: StateInput = None,
                                only_hidden: bool = False, step: int = 20,
                                offset: int = 0) -> List[models.UserQuestionPreview]:
        """
        Questions of a user.
        :param user: user (myself by default)
        :param state: state of the questions (open, voting, resolved; all by default)
        :param only_hidden: show only hidden questions
        :param step: number of questions
        :param offset: offset of the first question
        :return: list of questions
        """
        state = normalize_state(state)
        user = self._normalize_user(user)
        params: MethodArgs = {'n': step, 'p': offset, 'user': user}
        if only_hidden:
            params['hidden'] = 1
        if state is not None:
            params['state'] = str(state.value)
        data = self._call_checked('/v2/quserlist', params)
        return [factories.build_user_question_preview(q, self.categories) for q in data['qst']]

    def get_votes_page(self, option: OptionInput, step: int = 20, offset: int = 0) -> List[models.PollUserPreview]:
        """
        Votes for a poll option.
        :param option: poll option
        :param step: number of votes
        :param offset: offset of the first vote
        :return: list of votes
        """
        option = normalize_option(option)
        data = self._call_checked('/v2/whovoted', {'optid': option, 'n': step, 'p': offset})
        return [factories.build_poll_user_preview(u) for u in data['users']]

    def get_more_answers_page(self, question: QuestionInput, step: int = 20, offset: int = 0, sort: int = 1
                              ) -> List[models.Answer]:
        """
        Question answers.
        :param question: the question
        :param step: number of answers
        :param offset: offset of the first answer
        :return: list of answers
        """
        question = normalize_question(question)
        params = {'qid': question, 'n': step, 'p': offset, 'sort': sort}
        user_cache = {}
        data = self._call_checked('/v2/moreanswers', params)
        return [factories.build_answer(a, user_cache) for a in data['answers']]

    def get_user_answers_page(self, user: UserInput = None, only_best: bool = False, step: int = 20,
                              offset: int = 0) -> List[models.AnswerPreview]:
        """
        Answers of a user
        :param user: user (myself by default)
        :param only_best: show only best answers of a user
        :param step: number of answers
        :param offset: offset of the first answer
        :return: list of answers
        """
        user = self._normalize_user(user)
        params = {'n': step, 'p': offset, 'usrid': user}
        if only_best:
            params['best'] = 1
        data = self._call_checked('/v2/auserlist', params)
        return [factories.build_answer_preview(a, self.categories) for a in data['answers']]

    def get_watching_questions_page(self, user: UserInput = None, step: int = 20,
                                    offset: int = 0) -> List[models.MinimalQuestionPreview]:
        """
        Questions watched by a user.
        :param user: user (myself by default)
        :param step: number of questions
        :param offset: offset of the first question
        :return: list of watched questions
        """
        user = self._normalize_user(user)
        params = {'n': step, 'p': offset, 'id': user}
        data = self._call_checked('/v2/watchlist', params)
        return [factories.build_minimal_question_preview(q, self.categories) for q in (data['questions'] or [])]

    def get_likes_page(self, id: int, is_answer: bool, step: int = 20, offset: int = 0
                       ) -> List[models.SmallUserPreview]:
        """
        Users who liked a question  or an answer.
        :param id: object id
        :param is_answer: if the object is an answer
        :param step: number of likes
        :param offset: offset of the first like
        :return: list of users who liked this
        """
        params = {'n': step, 'p': offset, 'aid' if is_answer else 'qid': id}
        data = self._call_checked('/v2/marked', params)
        return [factories.build_small_user_preview(u) for u in data['marked']]

    def get_user_rating_page(self, rating_type: Union[str, models.RatingType] = "points", category: CategoryInput = None,
                             all_time: bool = False,
                             step: int = 20, offset: int = 0) -> List[models.User]:
        """
        User rating.
        :param rating_type: type of the rating
        :param category: category (all by default)
        :param all_time: show rating for all time
        :param step: number of users
        :param offset: offsetof the first user
        :return: list of users
        """
        params = {'n': step, 'p': offset, 'cat': '', 'type': 'points'}
        category = self._normalize_category(category) or ''
        rating_type = models.RatingType(rating_type)
        if all_time:
            params['all'] = 1
        else:
            params['type'] = rating_type.value
            if rating_type is models.RatingType.points:
                params['cat'] = category
        data = self._call_checked('/v2/usrrating', params)
        return [factories.build_user(u, {}) if all_time else factories.build_user_in_rating(u, rating_type) for u in
                data['rating']]

    def get_search_page(self, query: str, sort_by_date: bool = False, step: int = 20, offset: int = 0, *,
                        state: StateInput = None, category: CategoryInput = None, last_days: float = None,
                        questions_only: bool = False) -> List[models.QuestionSearchResult]:
        """
        Search questions.
        :param query: query string
        :param sort_by_date: sort by date, not by relevance
        :param step: number of results
        :param offset: offset of the first result
        :param state: search only questions with this state
        :param category: search in this category
        :param last_days: search only questions not older than this number of days
        :param questions_only: search only in question text
        :return: list of questions
        """
        params = {'num': step, 'sf': offset, 'q': query}
        if sort_by_date:
            params['sort'] = 'date'
        if state is not None:
            params['zvstate'] = {'A': 3, 'V': 2, 'R': 1}[normalize_state(state).value]
        if category is not None:
            params['zVCat'] = self._normalize_category_object(category).id
        if last_days is not None:
            params['zdts'] = -int(last_days * 86400)
        if questions_only:
            params['question_only'] = 1
        data = self._call_checked('https://otvet.mail.ru/go-proxy/answer_json', params, direct=True)
        return [factories.build_question_search_result(q, self.categories) for q in data['results']]

    def get_followers_page(self, user: UserInput = None, reverse: bool = False, step: int = 20, offset: int = 0
                           ) -> List[models.SmallUserPreview]:
        """
        User followers
        :param user: user (myself by default)
        :param reverse: show those whom the user follows, not his followers
        :param step: number of users
        :param offset: offset of the first user
        :return: list of followers
        """
        user = self._normalize_user(user)
        params = {'id': user, 'n': step, 'p': offset}
        if reverse:
            params['reverse'] = 1
        data = self._call_checked('/v2/who_follow', params)
        return [(factories.build_small_user_preview if reverse else factories.build_follower_preview)(u) for u in
                data['followers']]

    def get_blacklist_page(self, step: int = 20, offset: int = 0) -> List[models.SmallUserPreview]:
        """
        Blacklisted users.
        :param step: number of users
        :param offset: offset of the first user
        :return: list of blacklisted users
        """
        self._ensure_authenticated()
        params = {'bid': self.user_id, 'n': step, 'p': offset}
        data = self._call_checked('/v2/listblist', params)
        return [factories.build_small_user_preview(u) for u in data['list']]


    def get_promoted_leader_questions(self, category: CategoryInput = None) -> List[models.QuestionPreview]:
        """
        Leader questions displayed on the left.
        :param category: category (all by default)
        :return: list of questions
        """
        category = self._normalize_category(category) or ''
        return self.get_questions_page(None, category, only_leaders=True, step=None)

    def get_comments(self, reference: Union[int, models.BaseQuestion, models.BaseAnswer],
                     reference_type: Union[str, models.CommentType] = None) -> List[models.Comment]:
        """
        Comments to an answer or a poll.
        :param reference: answer or poll
        :param reference_type: type of an object (Q or A), required when the reference is an id
        :return:
        """
        if isinstance(reference, models.BaseQuestion):
            reference_type = models.CommentType.question
            reference = reference.id
        elif isinstance(reference, models.BaseAnswer):
            reference_type = models.CommentType.answer
            reference = reference.id
        elif isinstance(reference_type, str):
            reference_type = models.CommentType(reference_type)
        elif reference_type is None:
            raise error.OtvetArgumentError('reference_type is required for numeric reference')
        data = self._call_checked('/v2/all_comments', {'refid': reference, 'type': reference_type.value})
        user_cache = {}
        return [factories.build_comment(c, user_cache) for c in data['comments']['comments']]

    def get_limits(self) -> models.Limits:
        """
        Daily limits
        :return: limits object
        """
        self._ensure_authenticated()
        data = self._call_checked('/v2/showlimits', {})
        return factories.build_limits(data)

    def get_similar_questions(self, query: str) -> List[models.SimilarQuestionSearchResult]:
        """
        Similar questions.
        :param query: question text
        :return: list of similar questions
        """
        params = {'keyword': query}
        data = self._call_checked('/search/search', params)
        return [factories.build_similar_question_search_result(q, self.categories) for q in data['search']]

    def get_search_suggestions(self, query: str) -> List[str]:
        """
        Question search suggestions.
        :param query: query prefix
        :return: list of suggestions
        """
        params = {'q': query}
        data = self._call_checked('https://suggests.go.mail.ru/sg_otvet_u', params, direct=True)
        return [r['text'] for r in data['items']]

    def get_settings(self) -> models.Settings:
        """
        Current user settings
        :return: settings object
        """
        self._ensure_authenticated()
        data = self._call_checked('/v2/showsettings', {})
        return factories.build_settings(data)


    def iterate_questions(self, state: StateInput = 'A', category: CategoryInput = None, *,
                          category_exclude: str = '', step: int = 20, only_leaders: bool = False
                          ) -> Iterator[List[models.QuestionPreview]]:
        """
        Lists of questions, from new to old.
        :param state: state of the questions (open, voting, resolved), open by default
        :param category: category of the questions (all by default)
        :param step: size of one list
        :param only_leaders: return only leader questions
        :return: lists of questions
        """
        data = self.get_questions_page(state, category, step, category_exclude=category_exclude,
                                       only_leaders=only_leaders)
        lastid = data[0].id
        for p in itertools.count(step, step):
            yield data
            data = self.get_questions_page(state, category, step, p, lastid, category_exclude=category_exclude,
                                           only_leaders=only_leaders)
            if not data:
                return

    def iterate_best_questions(self, category: CategoryInput = None, *, step: int = 20
                               ) -> Iterator[List[models.BestQuestionPreview]]:
        """
        Lists of best questions, from new to old.
        :param category: category of the questions (all by default)
        :param step: size of one list
        :return: lists of questions
        """
        data = self.get_best_questions_page(category, step)
        lastid = data[0].id
        for p in itertools.count(step, step):
            yield data
            data = self.get_best_questions_page(category, step, p, lastid)
            if not data:
                return

    def iterate_new_questions(self, state: StateInput = 'A', category: CategoryInput = None, *,
                              category_exclude: str = '', step: int = 20,
                              delay: float = 10, include_first_batch: bool = True
                              ) -> Iterator[List[models.QuestionPreview]]:
        """
        Lists of new questions, as they appear.
        If questions are asked too fast, some of them may be skipped.
        :param state: state of the questions (open, voting, resolved), open by default
        :param category: category of the questions (all by default)
        :param step: maximal size of one list
        :param delay: interval between checks in seconds
        :param include_first_batch: return the last batch of questions that existed before the call (yes by defaullt)
        :return: lists of questions
        """
        last_call = time.time()
        data = self.get_questions_page(state, category, step, category_exclude=category_exclude)
        lastid = data[0].id
        if include_first_batch:
            yield data
        while True:
            time.sleep(max(0., last_call + delay - time.time()))
            last_call = time.time()
            data = self.get_questions_page(state, category, step, category_exclude=category_exclude)
            batch = [q for q in data if q.id > lastid]
            if batch:
                lastid = data[0].id
                yield batch

    def iterate_user_questions(self, user: UserInput = None, state: StateInput = None, *,
                               only_hidden: bool = False, step: int = 20
                               ) -> Iterator[List[models.UserQuestionPreview]]:
        """
        Lists of questions asked by a user.
        :param user: user (myself by default)
        :param state: state of the questions (open, voting, resolved), all by default
        :param only_hidden: show only hidden questions
        :param step: size of one list
        :return: lists of questions
        """
        yield from iterate_pages(lambda p: self.get_user_questions_page(user, state, only_hidden, step, p), step)

    def iterate_answers(self, question: QuestionInput, *, step: int = 20,
                        infinite: bool = False, delay: float = 10) -> Iterator[List[models.Answer]]:
        """
        Lists of answers to a question.
        :param question: question. If the question object contains some answers by itself they are returned first
        :param step: size of one list (except maybe the first one)
        :param infinite: yield new answers as they appear
        :param delay: interval between checks in seconds
        :return: lists of answers
        """
        if getattr(question, 'answer_count', None) == 0 and not infinite:
            return
        if not isinstance(question, models.Question):
            question = self.get_question(question, answer_count=step)
        if question.answers:
            yield question.answers
        offset = len(question.answers)
        if offset < question.answer_count:
            while True:
                answers = self.get_more_answers_page(question.id, step, offset)
                if answers:
                    yield answers
                offset += len(answers)
                if len(answers) < step:
                    break
        if not infinite:
            return
        last_call = time.time()
        while True:
            time.sleep(max(0., last_call + delay - time.time()))
            last_call = time.time()
            answers = self.get_more_answers_page(question.id, step, offset)
            if answers:
                yield answers
            offset += len(answers)

    def iterate_votes(self, option: OptionInput, *, step: int = 20) -> Iterator[List[models.PollUserPreview]]:
        """
        Lists of votes for a poll option.
        :param option: poll option
        :param step: size of one list
        :return: lists of votes
        """
        yield from iterate_pages(lambda p: self.get_votes_page(option, p, step), step)

    def iterate_user_answers(self, user: UserInput = None, only_best: bool = False, *, step: int = 20
                             ) -> Iterator[List[models.AnswerPreview]]:
        """
        Lists of answers of a user.
        :param user: user (myself by default)
        :param only_best: return only best answers
        :param step: size of one list
        :return: lists of answers
        """
        yield from iterate_pages(lambda p: self.get_user_answers_page(user, only_best, step, p), step)

    def iterate_watching_questions(self, user: UserInput = None, *, step: int = 20
                                   ) -> Iterator[List[models.MinimalQuestionPreview]]:
        """
        Lists of questions watched by a user.
        :param user: user (myself by default)
        :param step: size of one lists
        :return: lists of questions
        """
        yield from iterate_pages(lambda p: self.get_watching_questions_page(user, step, p), step)

    def iterate_question_likes(self, question: QuestionInput, *, step: int = 20) -> Iterator[List[models.SmallUserPreview]]:
        """
        Lists of users who liked a question.
        :param question: question
        :param step: size of one list
        :return: lists of users
        """
        question = normalize_question(question)
        yield from iterate_pages(lambda p: self.get_likes_page(question, False, step, p), step)

    def iterate_answer_likes(self, answer: AnswerInput, *, step: int = 20) -> Iterator[List[models.SmallUserPreview]]:
        """
        Lists of users who liked an answer.
        :param answer: answer
        :param step: size of one list
        :return: lists of user
        """
        answer = normalize_answer(answer)
        yield from iterate_pages(lambda p: self.get_likes_page(answer, True, step, p), step)

    def iterate_all_time_user_rating(self, *, step: int = 20) -> Iterator[List[models.User]]:
        """
        Lists of users in the rating of all time.
        :param step: size of one list
        :return: lists of users
        """
        yield from iterate_pages(lambda p: self.get_user_rating_page(all_time=True, step=step, offset=p), step)

    def iterate_user_rating_by_answers(self, *, step: int = 20) -> Iterator[List[models.UserInRating]]:
        """
        Lists of users in the weekly rating by answers.
        :param step: size of one list
        :return: lists of users
        """
        yield from iterate_pages(
            lambda p: self.get_user_rating_page(models.RatingType.answer_count, step=step, offset=p), step)

    def iterate_user_rating_by_best_answers(self, *, step: int = 20) -> Iterator[List[models.UserInRating]]:
        """
        Lists of users in the weekly rating by best answers.
        :param step: size of one list
        :return: lists of users
        """
        yield from iterate_pages(
            lambda p: self.get_user_rating_page(models.RatingType.best_answer_count, step=step, offset=p), step)

    def iterate_user_rating_by_points(self, category: CategoryInput = None, *, step: int = 20
                                      ) -> Iterator[List[models.UserInRating]]:
        """
        Lists of users in the weekly rating by points.
        :param category: category (all by default)
        :param step: size of one list
        :return: lists of users
        """
        yield from iterate_pages(lambda p: self.get_user_rating_page(category=category, step=step, offset=p),
                                 step)

    def iterate_search(self, query: str, sort_by_date: bool = False, *, step: int = 20,
                       state: StateInput = None, category: CategoryInput = None, last_days: float = None,
                       questions_only: bool = False) -> Iterator[List[models.QuestionSearchResult]]:
        """
        Lists of questions returned by search.
        :param query: query string
        :param sort_by_date: whether to sort by date, not by relevance
        :param step: size of one list
        :param state: search only questions with this state
        :param category: search in this category
        :param last_days: search only questions not older than this number of days
        :param questions_only: search only in question text
        :return: lists of questions
        """
        yield from iterate_pages(lambda p: self.get_search_page(query, sort_by_date, step, p, state=state, category=category,
                                                                last_days=last_days, questions_only=questions_only), step)

    def iterate_following(self, user: UserInput = None, *, step: int = 20) -> Iterator[List[models.SmallUserPreview]]:
        """
        Iterate the users whom a given user follows.
        :param user: user (myself by default)
        :param step: size of one list
        :return: lists of users
        """
        yield from iterate_pages(lambda p: self.get_followers_page(user, True, step, p), step)

    def iterate_followers(self, user: UserInput = None, *, step: int = 20) -> Iterator[List[models.FollowerPreview]]:
        """
        Iterate the followers of a user.
        :param user: user (myself by default)
        :param step: size of one list
        :return: lists of users
        """
        yield from iterate_pages(lambda p: self.get_followers_page(user, False, step, p), step)

    def iterate_blacklist(self, *, step: int = 20) -> Iterator[List[models.SmallUserPreview]]:
        """
        Iterate the blacklist.
        :param step: sizeof one list
        :return: lists of users
        """
        yield from iterate_pages(lambda p: self.get_blacklist_page(step, p), step)


    def get_question(self, question: QuestionInput, *, answer_count: int = 20) -> models.Question:
        """
        A full question object.
        :param question: question
        :param answer_count: how many answer to prefetch (use iterate_answers to get all of them)
        :return: question object
        """
        question = normalize_question(question)
        params = {'qid': question, 'n': answer_count, 'p': 0, 'sort': 1}
        data = self._call_checked('/v2/question', params)
        return factories.build_question(data, self.categories)

    def get_user(self, user: UserInput = None) -> models.UserProfile:
        """
        A full user profile object.
        Returns MyUserProfile when possible.
        :param user: user
        :return: user profile object
        """
        user = self._normalize_user(user)
        data = self._call_checked('/v2/stats_ex', {'user': user})
        return factories.build_user_profile(data, user)


    def _normalize_category_object(self, category: CategoryInput) -> models.Category:
        if isinstance(category, models.Category):
            return category
        category = self._normalize_category(category)
        if not category:
            raise error.OtvetArgumentError('A category is required')
        return self.categories.by_urlname(category)

    def _ensure_child_category(self, category: models.Category) -> None:
        if category.children:
            raise error.OtvetArgumentError('Asking questions is allowed only in categories without subcategories')

    def _add_question(self, category: CategoryInput, params: dict) -> int:
        self._ensure_authenticated()
        category = self._normalize_category_object(category)
        self._ensure_child_category(category)
        if category.parent:
            params['cid'] = category.parent.id
            params['subcid'] = category.id
        else:
            params['cid'] = category.id
        data = self._call_checked('/v2/addqst', params)
        return int(data['qid'])

    def add_question(self, category: CategoryInput, title: str, text: str = "", *,
                     allow_comments: bool = True, watch: bool = True) -> int:
        """
        Ask a question.
        :param category: category
        :param title: question title
        :param text: question text
        :param allow_comments: whether to allow comments to answers
        :param watch: whether to get notifications about answers
        :return: question id
        """
        params = {'Body': text, 'qtext': title, 'cancmt': int(bool(allow_comments)), 'watch': int(bool(watch))}
        return self._add_question(category, params)

    def add_poll(self, category: CategoryInput, title: str, poll_options: List[str],
                 text: str = "", allow_multiple: bool = False, *,
                 allow_comments: bool = True, watch: bool = True) -> int:
        """
        Create a poll.
        :param category: category
        :param title: poll title
        :param poll_options: list of poll options
        :param text: poll text
        :param allow_multiple: whether to allow multiple votes
        :param allow_comments: whether to allow comments
        :param watch: whether to get notifications about votes
        :return: question id
        """
        params = {'Body': text, 'qtext': title, 'cancmt': int(bool(allow_comments)), 'watch': int(bool(watch)),
                  'poll': 'C' if allow_multiple else 'S', 'poll_options[]': poll_options}
        return self._add_question(category, params)

    def edit_question(self, question: QuestionInput, category: CategoryInput = None, title: str = None,
                      text: str = None, poll_options: List[str] = None) -> models.Question:
        """
        Edit a question.
        :param question: question to edit
        :param category: new category
        :param title: new title
        :param text: new text
        :param poll_options: new poll options
        :return: edited question object
        """
        self._ensure_authenticated()
        if not isinstance(question, models.Question):
            question = self.get_question(question)
        if not question.edit_token:
            raise error.OtvetArgumentError('Cannot edit this question')
        current_poll_options = question.poll.options if question.poll else []
        params = {'id': question.id, 'edit_token': question.edit_token, 'header': question.title,
                  'text': question.text, 'cid': question.category.id,
                  'poll_options[]': [f'{o.id}:{o.text}' for o in current_poll_options]}
        utils.update_not_none(params, {'header': title, 'text': text})
        if category is not None:
            category = self._normalize_category_object(category)
            self._ensure_child_category(category)
            params['cid'] = category.id
        if poll_options is not None:
            if len(poll_options) > len(current_poll_options):
                raise error.OtvetArgumentError('Cannot add more options when editing a poll')
            params['poll_options[]'] = [f'{o.id}:{t}' for o, t in zip(current_poll_options, poll_options)]
        data = self._call_checked('/v2/editqst', params)
        return factories.build_question(data, self.categories)

    def add_answer(self, question: QuestionInput, text: str) -> int:
        """
        Answer a question.
        :param question: question
        :param text: answer text
        :return: qnswer id
        """
        self._ensure_authenticated()
        question = normalize_question(question)
        params = {'qid': question, 'Body': text}
        data = self._call_checked('/v2/addans', params)
        return int(data['result']['id'])

    def edit_answer(self, question: QuestionInput, answer: AnswerInput, text: str) -> None:
        """
        Edit an answer.
        :param question: question
        :param answer: answer
        :param text: new answer text
        """
        self._ensure_authenticated()
        question = normalize_question(question)
        answer = normalize_answer(answer)
        params = {'qid': question, 'update': answer, 'Body': text}
        self._call_checked('/v2/editans', params)

    def add_question_addition(self, question: QuestionInput, text: str) -> int:
        """
        Add something to a question.
        :param question: question
        :param text: addition text
        :return: addition id
        """
        self._ensure_authenticated()
        question = normalize_question(question)
        params = {'qid': question, 'Body': text}
        data = self._call_checked('/v2/updqst', params)
        return int(data['adnid'])

    def _add_comment(self, text: str, params: dict) -> int:
        self._ensure_authenticated()
        params = {'Body': text, 'source': '', **params}
        data = self._call_checked('/v2/addcmt', params)
        return int(data['cmid'])

    def add_answer_comment(self, answer: AnswerInput, text: str, reply_comment: CommentInput = None) -> int:
        """
        Comment an answer.
        :param answer: answer
        :param text: comment text
        :param reply_comment: a comment to reply to
        :return: comment id
        """
        if reply_comment is None:
            answer = normalize_answer(answer)
            return self._add_comment(text, {'refid': answer, 'type': 'A'})
        else:
            reply_comment = normalize_comment(reply_comment)
            return self._add_comment(text, {'cmid': reply_comment})

    def add_poll_comment(self, question: QuestionInput, text: str, reply_comment: CommentInput = None) -> int:
        """
        Comment a poll.
        :param question: question
        :param text: comment text
        :param reply_comment: a comment to reply to
        :return: comment id
        """
        question = normalize_question(question)
        if reply_comment is None:
            return self._add_comment(text, {'refid': question, 'type': 'Q'})
        else:
            reply_comment = normalize_comment(reply_comment)
            return self._add_comment(text, {'refid': question, 'type': 'Q', 'cmid': reply_comment})

    def vote_in_poll(self, question: QuestionInput, options: List[OptionInput]) -> None:
        """
        Vote in a poll.
        :param question: question
        :param options: options to vote for (only one is allowed for polls without multiple choice)
        """
        self._ensure_authenticated()
        question = normalize_question(question)
        options = [normalize_option(o) for o in options]
        params = {'qid': question, 'vote[]': options}
        self._call_checked('/v2/votepoll', params)

    def vote_for_best_answer(self, question: QuestionInput, answer: AnswerInput) -> None:
        """
        Vote for the best answer in a question.
        :param question: question
        :param answer: selected answer
        """
        self._ensure_authenticated()
        question = normalize_question(question)
        answer = normalize_answer(answer)
        params = {'qid': question, 'aid': answer}
        self._call_checked('/v2/votefor', params)

    def _like(self, params: dict, remove: bool) -> None:
        self._ensure_authenticated()
        self._call_checked('/v2/' + ('unmark' if remove else 'mark'), params)

    def like_question(self, question: QuestionInput, remove: bool = False) -> None:
        """
        Like a question
        :param question: question
        :param remove: whether to remove the like
        """
        question = normalize_question(question)
        self._like({'qid': question}, remove)

    def like_answer(self, answer: AnswerInput, remove: bool = False) -> None:
        """
        Like an answer
        :param answer: answer
        :param remove: whether to remove the like
        """
        answer = normalize_answer(answer)
        self._like({'aid': answer}, remove)

    def choose_best_answer(self, answer: AnswerInput) -> None:
        """
        Choose the best answer in a question.
        :param answer: answer
        """
        self._ensure_authenticated()
        answer = normalize_answer(answer)
        self._call_checked('/v2/selectbest', {'aid': answer})

    def watch_question(self, question: QuestionInput, drop: bool = False) -> None:
        """
        Watch a question and get notifications about new answers to it.
        :param question: questions
        :param drop: whether to stop watching
        """
        self._ensure_authenticated()
        question = normalize_question(question)
        self._call_checked('/v2/' + ('dropwatch' if drop else 'startwatch'), {'qid': question})

    def set_is_adult_flag(self) -> None:
        """
        Set is_adult flag to get access to some categories.
        """
        self._call_checked('/v2/iamadult', {})

    def follow_user(self, user: UserInput, unfollow: bool = False) -> None:
        """
        Follow a user
        :param user: a user to follow
        :param unfollow: whether to unfollow the user
        """
        self._ensure_authenticated()
        user = self._normalize_user(user)
        params = {'uid': user}
        self._call_checked('/v2/' + ('unfollow' if unfollow else 'follow'), params)

    def remove_follower(self, user: UserInput) -> None:
        """
        Remove a user from followers.
        :param user: user
        """
        self._ensure_authenticated()
        user = self._normalize_user(user)
        params = {'uid': user}
        self._call_checked('/v2/removefollower', params)

    def blacklist_user(self, user: UserInput, remove: bool = False) -> None:
        """
        Blacklist a follower
        :param user: user
        :param remove: whether to remove the user from the blacklist
        """
        self._ensure_authenticated()
        user = self._normalize_user(user)
        params = {'bid': user}
        self._call_checked('/v2/' + ('delblist' if remove else 'addblist'), params)

    def recommend_to_golden(self, question: QuestionInput) -> None:
        """
        Recommend a question to golden.
        :param question: question
        """
        self._ensure_authenticated()
        question = normalize_question(question)
        params = {'qid': question}
        self._call_checked('/v2/golden', params)

    def thank_answer(self, answer: AnswerInput) -> None:
        """
        Thank an answer (equivalent to liking by the question author).
        :param answer: answer
        """
        self._ensure_authenticated()
        answer = normalize_answer(answer)
        params = {'aid': answer}
        self._call_checked('/v2/thanks', params)

    def hide_answer(self, answer: AnswerInput, revert: bool = False) -> None:
        """
        Mark an answer as useless
        :param answer: answer
        :param revert: show the answer again
        """
        self._ensure_authenticated()
        answer = normalize_answer(answer)
        params = {'aid': answer}
        self._call_checked('/v2/' + ('unnotimportant' if revert else 'notimportant'), params)


# TODO notifications
# TODO gifts
# TODO abuse
# TODO is_adult without auth
# TODO company/expert page
# TODO change settings
# TODO add images and videos
# TODO see images and videos
# TODO localized errors
