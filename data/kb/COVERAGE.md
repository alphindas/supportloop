# Knowledge base coverage

Maps all 77 Banking77 intents to the article meant to answer them. **GAP** means the topic is left out on purpose, so the data loop has real gaps to find.

This file is documentation. It is **not** ingested, and the data-loop mining step must **not** read it. It is only used afterwards to score how many planted gaps mining found.

Covered intents: 76. Remaining gaps: 1 (`automatic_top_up`). Articles: 68.

**Data loop cycle 1** (2026-11-27) added 8 articles, drafted by Claude Code and not reviewed by a human; they fill 9 of the 10 planted gaps. The table of planted gaps below shows the original plan.

Mapping drafted by AI; not yet reviewed by a human. It says which article is *intended* to answer an intent, not that every message of that intent can be answered from it.

## Planted gaps

| Intent | Missing topic |
|---|---|
| `age_limit` | Minimum age |
| `apple_pay_or_google_pay` | Using phone wallets |
| `atm_support` | Which cash machines can be used |
| `automatic_top_up` | Automatic top-ups |
| `card_swallowed` | Card kept by a cash machine |
| `disposable_card_limits` | Disposable card limits |
| `edit_personal_details` | Changing name, address or other details |
| `get_disposable_virtual_card` | Getting a disposable card |
| `lost_or_stolen_phone` | Lost or stolen phone |
| `terminate_account` | Closing the account |

## All intents

| Intent | Article |
|---|---|
| `activate_my_card` | `activate-card` |
| `age_limit` | `minimum-age` |
| `apple_pay_or_google_pay` | `phone-wallets` |
| `atm_support` | `which-cash-machines` |
| `automatic_top_up` | **GAP** |
| `balance_not_updated_after_bank_transfer` | `bank-transfer-missing` |
| `balance_not_updated_after_cheque_or_cash_deposit` | `cash-deposit-missing` |
| `beneficiary_not_allowed` | `beneficiary-not-allowed` |
| `cancel_transfer` | `cancel-transfer` |
| `card_about_to_expire` | `card-expiry` |
| `card_acceptance` | `card-acceptance` |
| `card_arrival` | `card-delivery-times` |
| `card_delivery_estimate` | `card-delivery-times` |
| `card_linking` | `link-card` |
| `card_not_working` | `card-not-working` |
| `card_payment_fee_charged` | `extra-statement-charge` |
| `card_payment_not_recognised` | `unrecognised-card-payment` |
| `card_payment_wrong_exchange_rate` | `foreign-payment-wrong-rate` |
| `card_swallowed` | `card-kept-by-cash-machine` |
| `cash_withdrawal_charge` | `cash-withdrawals` |
| `cash_withdrawal_not_recognised` | `cash-withdrawal-unrecognised` |
| `change_pin` | `card-pin` |
| `compromised_card` | `compromised-card` |
| `contactless_not_working` | `contactless-payments` |
| `country_support` | `country-support` |
| `declined_card_payment` | `declined-card-payment` |
| `declined_cash_withdrawal` | `cash-withdrawal-declined` |
| `declined_transfer` | `transfer-failed` |
| `direct_debit_payment_not_recognised` | `direct-debit-unrecognised` |
| `disposable_card_limits` | `disposable-virtual-cards` |
| `edit_personal_details` | `change-personal-details` |
| `exchange_charge` | `exchange-fees` |
| `exchange_rate` | `exchange-rates` |
| `exchange_via_app` | `exchange-currency` |
| `extra_charge_on_statement` | `extra-statement-charge` |
| `failed_transfer` | `transfer-failed` |
| `fiat_currency_support` | `supported-cards-currencies` |
| `get_disposable_virtual_card` | `disposable-virtual-cards` |
| `get_physical_card` | `card-pin` |
| `getting_spare_card` | `spare-card` |
| `getting_virtual_card` | `virtual-card` |
| `lost_or_stolen_card` | `lost-or-stolen-card` |
| `lost_or_stolen_phone` | `lost-or-stolen-phone` |
| `order_physical_card` | `order-physical-card` |
| `passcode_forgotten` | `passcode-reset` |
| `pending_card_payment` | `card-payment-pending` |
| `pending_cash_withdrawal` | `cash-withdrawal-pending` |
| `pending_top_up` | `topup-pending` |
| `pending_transfer` | `transfer-pending` |
| `pin_blocked` | `card-pin` |
| `receiving_money` | `receiving-money` |
| `Refund_not_showing_up` | `refund-not-showing` |
| `request_refund` | `request-refund` |
| `reverted_card_payment?` | `card-payment-reversed` |
| `supported_cards_and_currencies` | `supported-cards-currencies` |
| `terminate_account` | `close-account` |
| `top_up_by_bank_transfer_charge` | `topup-fees` |
| `top_up_by_card_charge` | `topup-fees` |
| `top_up_by_cash_or_cheque` | `topup-by-cash` |
| `top_up_failed` | `topup-failed` |
| `top_up_limits` | `topup-limits` |
| `top_up_reverted` | `topup-reverted` |
| `topping_up_by_card` | `topup-by-card` |
| `transaction_charged_twice` | `charged-twice` |
| `transfer_fee_charged` | `transfer-fees` |
| `transfer_into_account` | `topup-by-bank-transfer` |
| `transfer_not_received_by_recipient` | `transfer-not-received` |
| `transfer_timing` | `transfer-timing` |
| `unable_to_verify_identity` | `verification-problems` |
| `verify_my_identity` | `verify-identity` |
| `verify_source_of_funds` | `source-of-funds` |
| `verify_top_up` | `topup-verification` |
| `virtual_card_not_working` | `virtual-card` |
| `visa_or_mastercard` | `card-acceptance` |
| `why_verify_identity` | `verify-identity` |
| `wrong_amount_of_cash_received` | `cash-wrong-amount` |
| `wrong_exchange_rate_for_cash_withdrawal` | `foreign-payment-wrong-rate` |
