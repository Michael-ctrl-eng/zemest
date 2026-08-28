import logging

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import get_settings
from app.models.crawl_job import CrawlJob
from app.models.order import Order
from app.models.tenant import Tenant

settings = get_settings()
logger = logging.getLogger(__name__)


async def notify_new_order(tenant: Tenant, order: Order) -> None:
    """Send notification to tenant owner about a new order."""
    if tenant.notification_pref == "email" and tenant.business_email:
        await _send_email_notification(tenant, order)
    else:
        logger.info(
            f"Order {order.order_number} for tenant {tenant.page_name} — "
            f"notification pref: {tenant.notification_pref}"
        )


async def _send_email_notification(tenant: Tenant, order: Order) -> None:
    """Send order notification email."""
    if not settings.SMTP_USER:
        logger.warning("SMTP not configured, skipping email notification")
        return

    items_text = ""
    for item in order.items:
        items_text += f"  - {item.product_name} x{item.quantity} = {item.total_price} EGP\n"

    body = f"""New Order Received! (تم استلام طلب جديد!)

Order: {order.order_number}
Customer: {order.customer_name}
Phone: {order.customer_phone}
Address: {order.address_detail}, {order.area or ''}, {order.city}, {order.governorate}
Payment: {order.payment_method.upper()}

Items:
{items_text}
Subtotal: {order.subtotal} EGP
Delivery: {order.delivery_charge} EGP
Total: {order.total} EGP

---
Zemest
"""

    msg = MIMEMultipart()
    msg["From"] = settings.NOTIFICATION_FROM_EMAIL
    msg["To"] = tenant.business_email
    msg["Subject"] = f"[{tenant.page_name}] New Order {order.order_number} - {order.total} EGP"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=True,
        )
        logger.info(f"Email sent for order {order.order_number}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


async def notify_low_quota(tenant: Tenant, usage_percent: float) -> None:
    """Notify tenant owner that their daily token usage is approaching the quota limit.

    Triggered when usage exceeds 80% of the tenant's daily token quota.
    Falls back to a log line when email is not configured, mirroring the
    graceful-failure pattern of ``notify_new_order``.
    """
    if tenant.notification_pref == "email" and tenant.business_email:
        await _send_low_quota_email(tenant, usage_percent)
    else:
        logger.info(
            f"Low-quota alert for tenant {tenant.page_name} — "
            f"usage at {usage_percent:.1f}% of daily quota "
            f"(notification pref: {tenant.notification_pref})"
        )


async def _send_low_quota_email(tenant: Tenant, usage_percent: float) -> None:
    """Send the low-quota warning email.

    Failures are logged and swallowed so that a SMTP outage never propagates
    into the request path that triggered the check.
    """
    if not settings.SMTP_USER:
        logger.warning("SMTP not configured, skipping low-quota email notification")
        return

    body = f"""Quota Warning — Daily Token Usage Near Limit
(تنبيه: اقتراب الاستخدام من الحد اليومي)

Page: {tenant.page_name}
Current usage: {usage_percent:.1f}% of the daily token quota.

Your Zemest agent is consuming tokens quickly. Consider reviewing your
automation rules, lowering the daily quota cap, or upgrading your plan
to avoid an interruption in service.

الاستخدام الحالي: {usage_percent:.1f}% من حصة الرموز اليومية. يُنصح بمراجعة
قواعد الأتمتة أو رفع الحصة اليومية لتجنب توقف الخدمة.

---
Zemest
"""

    msg = MIMEMultipart()
    msg["From"] = settings.NOTIFICATION_FROM_EMAIL
    msg["To"] = tenant.business_email
    msg["Subject"] = f"[{tenant.page_name}] تنبيه: اقتراب من حد الاستخدام"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=True,
        )
        logger.info(
            f"Low-quota email sent to {tenant.business_email} "
            f"for tenant {tenant.page_name} ({usage_percent:.1f}%)"
        )
    except Exception as e:
        logger.error(f"Failed to send low-quota email: {e}")


async def notify_crawl_complete(tenant: Tenant, job: CrawlJob) -> None:
    """Notify tenant owner that a website crawl job has finished.

    Reports the number of pages crawled and products extracted. Uses the same
    notification-pref + email dispatch pattern as ``notify_new_order`` and
    degrades gracefully when SMTP is not configured.
    """
    if tenant.notification_pref == "email" and tenant.business_email:
        await _send_crawl_complete_email(tenant, job)
    else:
        logger.info(
            f"Crawl complete for tenant {tenant.page_name} — "
            f"job {job.id}: {job.pages_found} pages, "
            f"{job.products_extracted} products "
            f"(notification pref: {tenant.notification_pref})"
        )


async def _send_crawl_complete_email(tenant: Tenant, job: CrawlJob) -> None:
    """Send the crawl-completion summary email.

    Any SMTP error is logged and swallowed so crawl pipeline code that calls
    this notifier never crashes because of an email outage.
    """
    if not settings.SMTP_USER:
        logger.warning("SMTP not configured, skipping crawl-complete email notification")
        return

    duration_text = ""
    if job.started_at and job.completed_at:
        delta = job.completed_at - job.started_at
        duration_text = f"Duration: {int(delta.total_seconds())}s\n"

    body = f"""Crawl Job Completed (اكتمل الزحف)

Page: {tenant.page_name}
URL: {job.url}
Status: {job.status}
Pages found: {job.pages_found}
Products extracted: {job.products_extracted}
{duration_text}
The new products have been added to your catalogue and the knowledge
base has been rebuilt. You can review them from the Products dashboard.

تمت إضافة المنتجات الجديدة إلى الكتالوج وإعادة بناء قاعدة المعرفة.
يمكنك مراجعتها من لوحة المنتجات.

---
Zemest
"""

    msg = MIMEMultipart()
    msg["From"] = settings.NOTIFICATION_FROM_EMAIL
    msg["To"] = tenant.business_email
    msg["Subject"] = (
        f"[{tenant.page_name}] اكتمل الزحف — "
        f"{job.pages_found} صفحات، {job.products_extracted} منتجات"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=True,
        )
        logger.info(
            f"Crawl-complete email sent for job {job.id} "
            f"({job.pages_found} pages, {job.products_extracted} products)"
        )
    except Exception as e:
        logger.error(f"Failed to send crawl-complete email: {e}")
