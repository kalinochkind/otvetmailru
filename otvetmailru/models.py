import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Union


class QuestionState(Enum):
    """Lifecycle stage of a question."""
    open = 'A'
    vote = 'V'
    resolve = 'R'


class PollType(Enum):
    """Type of a poll in a question, if it exists."""
    none = ''
    single = 'S'
    multiple = 'C'

    def __bool__(self):
        return bool(self.value)


class ThankStatus(Enum):
    """Reaction of a question author to an answer, like or dislike."""
    none = 0
    liked = 1
    hidden = -1

    def __bool__(self):
        return bool(self.value)


class CommentType(Enum):
    """Thing that was commented."""
    question = 'Q'
    answer = 'A'


class RatingType(Enum):
    """Type of user rating."""
    points = 'points'
    answer_count = 'anscnt'
    best_answer_count = 'bestanscnt'


class Avatar:
    """
    Avatar wrapper.
    :ivar filin: the filin parameter returned from the API
    """

    def __init__(self, filin: str):
        self.filin = filin

    def with_size(self, width: int, height: int) -> str:
        """
        Get a link to the avatar with the desired size.
        :param width: desired width
        :param height: desired height
        :return: avatar url
        """
        return str(self) + f'&width={width}&height={height}'

    def __str__(self):
        return f'https://filin.mail.ru/pic?d={self.filin}'

    def __repr__(self):
        return f'Avatar({self.filin!r})'


@dataclass(frozen=True, eq=False)
class Rate:
    """Level of a user."""
    name: str
    min_points: int
    min_kpd: float
    next: Optional['Rate'] = field(repr=False, default=None)
    next_by_kpd: Optional['Rate'] = field(repr=False, default=None)


@dataclass
class BaseUser:
    """Base class for a user."""
    id: int
    name: str
    avatar: Avatar

    def __eq__(self, other):
        """Compares with other BaseUsers by id"""
        return isinstance(other, BaseUser) and self.id == other.id

    @property
    def url(self) -> str:
        return f'https://otvet.mail.ru/profile/id{self.id}/'


@dataclass
class SmallUserPreview(BaseUser):
    rate: Rate


@dataclass
class CommentUserPreview(SmallUserPreview):
    points: int


@dataclass
class PollUserPreview(SmallUserPreview):
    email: str


@dataclass
class UserPreview(BaseUser):
    is_vip: bool
    kpd: float
    about: str
    is_expert: bool


@dataclass(eq=False, frozen=True)
class Category:
    """Question category."""
    id: int
    urlname: str
    name: str
    position: int
    is_readonly: bool
    parent: Optional['Category'] = field(repr=False)
    children: List['Category'] = field(repr=False)

    @property
    def url(self) -> str:
        return f'https://otvet.mail.ru/{self.urlname}/'


@dataclass
class BaseQuestion:
    """Base class for a question."""
    id: int
    title: str
    category: Category

    def __eq__(self, other):
        """Compares with other BaseQuestions by id."""
        return isinstance(other, BaseQuestion) and self.id == other.id

    @property
    def url(self) -> str:
        return f'https://otvet.mail.ru/question/{self.id}'


@dataclass
class SimpleQuestion(BaseQuestion):
    state: QuestionState
    age_seconds: int
    is_leader: bool
    poll_type: PollType
    answer_count: int


@dataclass
class QuestionPreview(SimpleQuestion):
    author: UserPreview


@dataclass
class BestQuestionPreview(QuestionPreview):
    can_like: bool
    like_count: int


@dataclass
class UserQuestionPreview(SimpleQuestion):
    is_hidden: bool


@dataclass
class User(UserPreview):
    points: int
    rate: Rate


@dataclass
class UserInRating(User):
    rating_type: RatingType
    rating_points: int


@dataclass
class Comment:
    """Comment to an answer or to a poll."""
    id: int
    text: str
    author_id: int
    author: Union[User, CommentUserPreview, None]
    age_seconds: int
    comment_count: int
    comments: List['Comment']
    parent_id: int
    reference_id: int
    number: int
    type: CommentType

    def __eq__(self, other):
        """Compares with other comments by id."""
        return isinstance(other, Comment) and self.id == other.id

    @property
    def url(self) -> str:
        return f'https://otvet.mail.ru/{self.type.name}/{self.reference_id}/cid-{self.id}'


@dataclass
class BaseAnswer:
    """Base class for an answer."""
    id: int
    text: str
    age_seconds: int

    def __eq__(self, other):
        """Compares with other BaseAnswers by id."""
        return isinstance(other, BaseAnswer) and self.id == other.id

    @property
    def url(self) -> str:
        return f'https://otvet.mail.ru/answer/{self.id}'


@dataclass
class Answer(BaseAnswer):
    author: User
    source: str
    can_like: bool
    can_thank: bool
    thank_status: ThankStatus
    like_count: int
    comment_count: int
    vote_count: int
    comments: List[Comment]


@dataclass
class QuestionAddition:
    """Piece of text added to a question."""
    id: int
    age_seconds: int
    text: str

    def __eq__(self, other):
        return isinstance(other, QuestionAddition) and self.id == other.id


@dataclass
class PollOption:
    """Option in a poll."""
    id: int
    text: str
    vote_count: int
    my_vote: bool

    def __eq__(self, other):
        return isinstance(other, PollOption) and self.id == other.id


@dataclass(eq=False)
class Poll:
    """Poll in a question."""
    type: PollType
    vote_count: int
    options: List[PollOption]
    i_voted: bool


@dataclass
class Question(SimpleQuestion):
    author: User
    best_answer: Optional[Answer]
    best_answer_vote_count: int
    can_choose_best_answer: bool
    liked_by: List[SmallUserPreview]
    like_count: int
    additions: List[QuestionAddition]
    comments: Optional[List[Comment]]
    comment_count: int
    answers: List[Answer]
    can_edit: bool
    can_comment: bool
    can_like: bool
    can_answer: bool
    can_add: bool
    cannot_answer_reason: Optional[str]
    created_at: datetime.datetime
    text: str
    is_hidden: bool
    is_watching: bool
    poll: Optional[Poll]
    deleted_by_id: Optional[int]
    can_recommend_to_golden: bool
    edit_token: Optional[str]


@dataclass
class UserProfile(User):
    """User profile page."""
    is_banned: bool
    is_followed_by_me: bool
    is_hidden: bool
    place: int
    answer_count: int
    best_answer_count: int
    deleted_answer_count: int
    question_count: int
    open_question_count: int
    voting_question_count: int
    resolved_question_count: int
    blacklisted_count: int
    followers_count: int
    following_count: int
    week_points: int


@dataclass
class MyUserProfile(UserProfile):
    """Profile page of myself, has a few extra fields."""
    watching_question_count: int  # watchcnt
    direct_question_count: int  # cnt
    removed_question_count: int  # cnt
    banned_until: Optional[datetime.datetime]


@dataclass
class LimitSet:
    """Limits for a day."""
    questions: int
    direct_questions: int
    answers: int
    best_answer_votes: int
    poll_votes: int
    likes: int
    photos: int
    videos: int
    best_question_recommends: int


@dataclass
class Limits:
    """Total limits for a day and remainders for today"""
    total: LimitSet
    current: LimitSet


@dataclass
class MinimalUserPreview(BaseUser):
    pass


@dataclass
class MinimalQuestionPreview(SimpleQuestion):
    author: MinimalUserPreview


@dataclass
class AnswerPreview(BaseAnswer):
    is_best: bool
    question: MinimalQuestionPreview


@dataclass
class QuestionSearchResult(BaseQuestion):
    text: str
    answer_count: int
    state: QuestionState
    is_poll: bool
    created_at: datetime.datetime
    age_seconds: int
    author: MinimalUserPreview


@dataclass
class SimilarQuestionSearchResult(BaseQuestion):
    pass


@dataclass
class FollowerPreview(SmallUserPreview):
    is_followed_by_me: bool


@dataclass
class Settings:
    news: bool
    sound: bool
    all_mail: bool
    all_web: bool
    answer_mail: bool
    answer_web: bool
    like_mail: bool
    like_web: bool
    comment_mail: bool
    comment_web: bool
    vote_mail: bool
    vote_web: bool
