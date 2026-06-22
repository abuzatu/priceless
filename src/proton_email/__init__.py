"""Proton Mail browser automation."""

from proton_email.login import (
    LibraOneTimeCode,
    LibraVoucherDetail,
    ProtonEmailLogin,
    ProtonEmailMessage,
    extract_all_voucher_url_and_code_pairs,
    extract_one_time_code,
    extract_voucher_order_fields,
    extract_voucher_url_and_code,
    parse_message_datetime,
)

__all__ = [
    "ProtonEmailLogin",
    "ProtonEmailMessage",
    "LibraOneTimeCode",
    "LibraVoucherDetail",
    "extract_one_time_code",
    "extract_voucher_url_and_code",
    "extract_all_voucher_url_and_code_pairs",
    "extract_voucher_order_fields",
    "parse_message_datetime",
]
