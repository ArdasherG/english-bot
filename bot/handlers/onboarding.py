"""
Онбординг нового пользователя — 4 вопроса.
Использует FSM (Finite State Machine) aiogram для пошагового диалога.
"""
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from api.services.database import create_user, update_user, get_user

router = Router()


class OnboardingStates(StatesGroup):
    waiting_level      = State()
    waiting_profession = State()
    waiting_interests  = State()
    waiting_goal       = State()
    waiting_lang       = State()


def level_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌱 Beginner — знаю совсем мало")],
            [KeyboardButton(text="📚 Intermediate — могу общаться")],
            [KeyboardButton(text="🚀 Advanced — хочу довести до совершенства")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def start_onboarding(message: Message, state: FSMContext):
    """Запускает онбординг для нового пользователя."""
    user = message.from_user
    await create_user(user.id, user.username or "", user.full_name)

    await message.answer(
        f"👋 Привет, *{user.first_name}*! Я твой персональный AI English Tutor.\n\n"
        "Давай я узнаю о тебе немного — это займёт минуту, "
        "зато примеры и объяснения будут подобраны именно для тебя 🎯\n\n"
        "*Какой у тебя уровень английского?*",
        parse_mode="Markdown",
        reply_markup=level_keyboard(),
    )
    await state.set_state(OnboardingStates.waiting_level)


@router.message(OnboardingStates.waiting_level)
async def process_level(message: Message, state: FSMContext):
    text = message.text or ""

    if "Beginner" in text:
        level = "beginner"
    elif "Intermediate" in text:
        level = "intermediate"
    else:
        level = "advanced"

    await state.update_data(level=level)

    await message.answer(
        "Отлично! 💪\n\n"
        "*Кем ты работаешь или на кого учишься?*\n"
        "_Например: врач, программист, студент-юрист, дизайнер..._",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(OnboardingStates.waiting_profession)


@router.message(OnboardingStates.waiting_profession)
async def process_profession(message: Message, state: FSMContext):
    await state.update_data(profession=message.text)

    await message.answer(
        "Интересно! 🙌\n\n"
        "*Что тебе нравится? Чем увлекаешься?*\n"
        "_Например: аниме, футбол, путешествия, музыка, кино..._\n"
        "_Можешь написать несколько через запятую_",
        parse_mode="Markdown",
    )
    await state.set_state(OnboardingStates.waiting_interests)


@router.message(OnboardingStates.waiting_interests)
async def process_interests(message: Message, state: FSMContext):
    # Разбиваем интересы по запятой
    interests = [i.strip() for i in (message.text or "").split(",") if i.strip()]
    await state.update_data(interests=interests)

    await message.answer(
        "Супер! 🌟\n\n"
        "*Зачем тебе английский? Какая главная цель?*\n"
        "_Например: работа в международной компании, переезд, сериалы без субтитров..._",
        parse_mode="Markdown",
    )
    await state.set_state(OnboardingStates.waiting_goal)


@router.message(OnboardingStates.waiting_goal)
async def process_goal(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(goal=message.text or "")
    await message.answer(
        "Отлично! 🌍\n\n"
        "*Как тебе удобнее получать объяснения и исправления?*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🇷🇺 На русском")],
                [KeyboardButton(text="🇬🇧 In English")],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    await state.set_state(OnboardingStates.waiting_lang)


@router.message(OnboardingStates.waiting_lang)
async def process_lang(message: Message, state: FSMContext):
    data = await state.get_data()
    interface_lang = "ru" if "русском" in (message.text or "") else "en"

    await update_user(
        message.from_user.id,
        level=data["level"],
        profession=data["profession"],
        interests=data["interests"],
        goal=data["goal"],
        interface_lang=interface_lang,
        onboarded=1,
    )
    await state.clear()

    interests_str = ", ".join(data["interests"]) if data["interests"] else "разное"

    if interface_lang == "ru":
        await message.answer(
            "🎉 *Профиль создан!*\n\n"
            f"📊 Уровень: *{data['level']}*\n"
            f"💼 Профессия: *{data['profession']}*\n"
            f"❤️ Интересы: *{interests_str}*\n"
            f"🎯 Цель: *{data['goal']}*\n\n"
            "Что умею:\n"
            "🎤 *Голосовое* — практика разговора\n"
            "📖 *Что значит X?* — объясню слово\n"
            "💬 */chat* — свободный диалог с носителем\n"
            "👤 */profile* — твой профиль",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await message.answer(
            "🎉 *Profile created!*\n\n"
            f"📊 Level: *{data['level']}*\n"
            f"💼 Profession: *{data['profession']}*\n"
            f"❤️ Interests: *{interests_str}*\n"
            f"🎯 Goal: *{data['goal']}*\n\n"
            "What I can do:\n"
            "🎤 *Voice message* — speaking practice\n"
            "📖 *What does X mean?* — word explanation\n"
            "💬 */chat* — free conversation with a native speaker\n"
            "👤 */profile* — your profile",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
