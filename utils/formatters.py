"""
Text Formatters and Helpers
Utilities for formatting bot messages
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import html


def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    if text is None:
        return ""
    return html.escape(str(text))


def format_datetime(dt: datetime, include_time: bool = True) -> str:
    """Format datetime for display"""
    if dt is None:
        return "N/A"

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt

    if include_time:
        return dt.strftime("%d.%m.%Y %H:%M")
    return dt.strftime("%d.%m.%Y")


def format_event(event: Dict[str, Any]) -> str:
    """Format event data for display"""
    title = escape_html(event.get("title", "Untitled"))
    location = escape_html(event.get("location", "N/A"))
    format_type = escape_html(event.get("format", "N/A"))
    description = escape_html(event.get("description", ""))

    event_date = event.get("event_date") or event.get("date")
    date_str = format_datetime(event_date) if event_date else "N/A"

    # Truncate long descriptions
    if len(description) > 500:
        description = description[:497] + "..."

    return (
        f"<b>{title}</b>\n\n"
        f"<b>Date:</b> {date_str}\n"
        f"<b>Location:</b> {location}\n"
        f"<b>Format:</b> {format_type}\n\n"
        f"<b>Description:</b>\n{description}"
    )


def format_course(course: Dict[str, Any]) -> str:
    """Format course data for display"""
    title = escape_html(course.get("title", "Untitled"))
    description = escape_html(course.get("description", ""))
    language = escape_html(course.get("language", "N/A"))
    duration = course.get("duration", 0)
    price = course.get("price", 0)
    currency = escape_html(course.get("currency", "KZT"))
    level = escape_html(course.get("level", "N/A"))

    # Format duration
    hours = duration // 60
    minutes = duration % 60
    duration_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"

    # Truncate long descriptions
    if len(description) > 500:
        description = description[:497] + "..."

    price_str = f"{price:,.0f} {currency}" if price else "Free"

    return (
        f"<b>{title}</b>\n\n"
        f"<b>Language:</b> {language}\n"
        f"<b>Duration:</b> {duration_str}\n"
        f"<b>Level:</b> {level}\n"
        f"<b>Price:</b> {price_str}\n\n"
        f"<b>Description:</b>\n{description}"
    )


def format_vacancy(vacancy: Dict[str, Any]) -> str:
    """Format vacancy data for display"""
    title = vacancy.get("title_ru") or vacancy.get("title_kz") or "Untitled"
    title = escape_html(title)
    description = vacancy.get("description_ru") or vacancy.get("description_kz") or ""
    description = escape_html(description)
    company = escape_html(vacancy.get("company_name", "N/A"))
    employment_type = escape_html(vacancy.get("employment_type", "N/A"))
    work_type = escape_html(vacancy.get("work_type", "N/A"))

    salary_min = vacancy.get("salary_min")
    salary_max = vacancy.get("salary_max")
    salary = vacancy.get("salary")

    if salary_min and salary_max:
        salary_str = f"{salary_min:,} - {salary_max:,} KZT"
    elif salary:
        salary_str = f"{salary:,} KZT"
    else:
        salary_str = "Negotiable"

    # Truncate long descriptions
    if len(description) > 500:
        description = description[:497] + "..."

    return (
        f"<b>{title}</b>\n\n"
        f"<b>Company:</b> {company}\n"
        f"<b>Employment:</b> {employment_type}\n"
        f"<b>Work Type:</b> {work_type}\n"
        f"<b>Salary:</b> {salary_str}\n\n"
        f"<b>Description:</b>\n{description}"
    )


def format_news(news: Dict[str, Any]) -> str:
    """Format news article for display"""
    title = news.get("title_ru") or news.get("title_kz") or news.get("title") or "Untitled"
    title = escape_html(title)
    content = news.get("content_ru") or news.get("content_kz") or news.get("content") or ""
    content = escape_html(content)
    category = escape_html(news.get("category", "N/A"))
    source = escape_html(news.get("source", "N/A"))

    published_at = news.get("published_at") or news.get("created_at")
    date_str = format_datetime(published_at) if published_at else "N/A"

    # Truncate long content
    if len(content) > 500:
        content = content[:497] + "..."

    return (
        f"<b>{title}</b>\n\n"
        f"<b>Date:</b> {date_str}\n"
        f"<b>Category:</b> {category}\n"
        f"<b>Source:</b> {source}\n\n"
        f"{content}"
    )


def format_project(project: Dict[str, Any]) -> str:
    """Format project data for display"""
    title = project.get("title_ru") or project.get("title_kz") or project.get("title") or "Untitled"
    title = escape_html(title)
    description = project.get("description_ru") or project.get("description_kz") or project.get("description") or ""
    description = escape_html(description)
    status = escape_html(project.get("status", "N/A"))

    # Truncate long descriptions
    if len(description) > 500:
        description = description[:497] + "..."

    return (
        f"<b>{title}</b>\n\n"
        f"<b>Status:</b> {status}\n\n"
        f"<b>Description:</b>\n{description}"
    )


def format_list_item(item: Dict[str, Any], index: int, module: str) -> str:
    """Format a single list item"""
    if module == "events":
        title = escape_html(item.get("title", "Untitled"))
        date = format_datetime(item.get("event_date") or item.get("date"), include_time=False)
        return f"{index}. <b>{title}</b> - {date}"

    elif module == "courses":
        title = escape_html(item.get("title", "Untitled"))
        price = item.get("price", 0)
        price_str = f"{price:,.0f} KZT" if price else "Free"
        return f"{index}. <b>{title}</b> - {price_str}"

    elif module == "vacancies":
        title = item.get("title_ru") or item.get("title_kz") or "Untitled"
        title = escape_html(title)
        company = escape_html(item.get("company_name", ""))
        return f"{index}. <b>{title}</b> - {company}"

    elif module == "news":
        title = item.get("title_ru") or item.get("title_kz") or item.get("title") or "Untitled"
        title = escape_html(title)
        return f"{index}. <b>{title}</b>"

    elif module == "projects":
        title = item.get("title_ru") or item.get("title_kz") or item.get("title") or "Untitled"
        title = escape_html(title)
        return f"{index}. <b>{title}</b>"

    else:
        title = escape_html(item.get("title", item.get("name", f"Item {item.get('id')}")))
        return f"{index}. <b>{title}</b>"


def format_list(items: List[Dict[str, Any]], module: str, page: int = 1, page_size: int = 10) -> str:
    """Format a list of items"""
    if not items:
        return f"No {module} found."

    lines = []
    for i, item in enumerate(items, start=(page - 1) * page_size + 1):
        lines.append(format_list_item(item, i, module))

    return "\n".join(lines)


def format_error(error_message: str) -> str:
    """Format error message"""
    return f"Error: {escape_html(error_message)}"


def format_session_info(session) -> str:
    """Format session information for display"""
    return (
        f"<b>Session Info</b>\n\n"
        f"<b>Admin ID:</b> {session.admin_id}\n"
        f"<b>Role:</b> {session.role}\n"
        f"<b>Telegram ID:</b> {session.telegram_user_id}\n"
        f"<b>Created:</b> {format_datetime(session.created_at)}\n"
        f"<b>Last Activity:</b> {format_datetime(session.last_activity)}"
    )
