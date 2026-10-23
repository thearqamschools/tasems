# WhatsApp integration — what it needs and what it costs (23 Oct 2026)

**Status: not built. Needs the project lead's approval of the cost (no paid service without approval).**

## What The Arqam Schools want
1. **Monthly vouchers:** one "Send" button sends every child's fee voucher (PDF) to the father's and/or mother's
   WhatsApp, for the whole school.
2. **Send again:** after a voucher is changed (amount up or down), send it again to the father, the mother or both.
3. **Birthdays:** on each child's date of birth, a birthday wish from the school to the parents (mother's number).
4. **Custom messages:** a portal to choose the whole school, a class or a section and send a message
   (school timings, holidays, any notice) to all those parents in one click.

## Can it be free?
- **Today (free, already in TASEMS):** Notices → Messages prepares each parent's message and opens WhatsApp with
  it filled in (wa.me link). Someone still presses Send for each parent. Fine for a few parents; not for a
  whole school in one click.
- **WhatsApp Business app broadcast lists (free):** manual, up to 256 contacts per list, and only parents who
  saved the school's number receive it. Not connected to TASEMS.
- **Unofficial "WhatsApp Web" bulk tools:** against WhatsApp's terms; numbers get banned. **Not recommended.**
- **One-click sending from TASEMS needs the official WhatsApp Business Platform (Cloud API) from Meta, which
  charges per message.** There is no free official way to send in bulk.

## How Meta charges (per message delivered)
| Message type (Meta's category) | Our use | Pakistan rate (USD per message) |
|---|---|---|
| Utility | Fee vouchers, voucher re-sends, fee reminders, school notices (timings, holidays) | about **$0.010–0.015** |
| Marketing | Birthday wishes, greetings, admission campaigns | about **$0.047** |
| Service (school replying to a parent within 24 h) | Answering parents | first **1,000 a month free** per number, then about the utility rate |

**To confirm before approval:** Meta raised Pakistan's utility rate on 1 April 2026 (to about $0.010) and again
from 1 October 2026 (reported as about $0.015); these figures come from Meta partners, not from Meta's own rate
card, which must be checked when the account is opened. Meta decides each template's category when it approves
it; a general announcement may be classed as marketing.

## Estimate (network figures: 200,000+ students)
Dollar figures only; the rupee cost depends on the bank's dollar rate on the day.

| Item | Messages a month | Cost a month (USD) |
|---|---|---|
| Vouchers to **one** parent | about 200,000 | about $2,000–3,000 |
| Vouchers to **father and mother** | about 400,000 | about $4,000–6,000 |
| Birthday wish to the mother | about 16,700 (200,000 ÷ 12) | about $790 |
| One notice to every parent (once) | about 200,000 | about $2,000–3,000 (utility) or about $9,500 (marketing) |
| Voucher re-sends | as many as are sent | $0.010–0.015 each |

**Per average branch** (about 670 students): vouchers to one parent about $7–10, to both parents about $14–20,
birthdays about $2.60, one notice to all parents about $7–10 (utility) a month.

Family vouchers (one voucher per family) and sending to one parent by default reduce the cost.

## Ways to connect
| Option | Monthly fee | Notes |
|---|---|---|
| **Meta Cloud API directly (recommended)** | None; only Meta's per-message charges | TASEMS sends the messages itself, so a partner's portal is not needed. Payment to Meta by card in USD. |
| A Meta partner (BSP) in Pakistan | Partner fee on top of Meta's charges (varies by partner) | Gives their own dashboard and support; TASEMS would still connect to it. |

## Process
1. **Meta Business account** for The Arqam Schools, and **business verification** (registration / NTN
   documents, address, website www.thearqam.com — the name must match the documents).
2. **A WhatsApp number for sending.** A new SIM is simplest. If the existing 0339-2406479 is moved to the API,
   it may stop working in the normal WhatsApp app unless Meta's "coexistence" option is available for it —
   to check at setup.
3. **Display name** "The Arqam Schools" approved by Meta (optional verified badge later).
4. **Message templates** approved by Meta (usually within a day): fee voucher (with the PDF), voucher updated,
   birthday wish, notice — in English and Urdu.
5. **Payment method** (international card) added in Meta's billing.
6. **Sending limits:** a new number starts with a small daily limit of new parents per day; Meta raises it
   step by step when messages are delivered and not blocked. A whole network in one click needs the higher
   limit first, so sending starts branch by branch.
7. **Parents' consent:** parents should agree to receive WhatsApp messages from the school (a tick on the
   admission form / parent portal); parents can stop messages at any time.

## What TASEMS would add (after approval)
- **WhatsApp page:** choose whole school / class / section / defaulters / one family; father, mother or both;
  message type; see how many messages and the estimated cost; then **Send**.
- **Monthly vouchers:** "Send to WhatsApp" on the vouchers page for the month; "Send again" on a single voucher
  after a change.
- **Birthdays:** sent automatically each morning to parents of children born on that day (can be switched off).
- **Delivery report:** sent, delivered, read or failed, per parent; failed numbers listed for correction.
- Messages go out in the background a few at a time, within Meta's limits; every send is recorded (who, when,
  how many).

Development time is part of the ongoing work; no extra hosting cost (Meta's delivery reports reach the existing
server over HTTPS).

## Sources (third-party reports of Meta's rates, Oct 2026)
- Meta: Pricing on the WhatsApp Business Platform — https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing
- YCloud: pricing update 1 April 2026 — https://www.ycloud.com/blog/whatsapp-api-message-pricing-update-effective-april-1-2026
- YCloud: pricing update 1 October 2026 — https://www.ycloud.com/blog/whatsapp-api-message-pricing-update-effective-october-1-2026
- Digiteazy: WhatsApp Business API pricing in Pakistan (2026) — https://digiteazy.com/whatsapp-business-api-pricing-pakistan/
- Ominiflow: Pakistan WhatsApp API pricing 2026 — https://ominiflow.com/whatsapp-api-pricing/pakistan
- Respond.io: WhatsApp API pricing 2026 — https://respond.io/blog/whatsapp-business-api-pricing
