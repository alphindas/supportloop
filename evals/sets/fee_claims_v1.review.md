# Fee test claims: review sheet

Claims drafted by Claude Code, not reviewed. Expected labels are left out on purpose.

Mark each claim against the article shown above it:
- **correct**: everything in the claim is supported by the article.
- **wrong**: some part contradicts the article or is not in it.
- **unsure**: you cannot decide, or the wording is unclear.

## Article `topup-fees`

```
## Card top-ups
- UK debit card: free.
- EEA debit card: free.
- Credit card: 1.5% of the amount.
- Card issued outside the UK and EEA: 2.0% of the amount.

If both card rules apply, only the higher fee is charged. The fee is shown before you confirm.

## Bank transfers
NovaPay does not charge for UK or SEPA bank transfer top-ups. For international (SWIFT) transfers, banks along the way may deduct their own charges.

## Cash
Cash deposits have a fee of 1.5%.
```

- **fee-01** A credit card issued outside the UK and EEA is charged 1.5% to top up.
- **fee-02** NovaPay does not charge for SEPA bank transfer top-ups.
- **fee-03** Topping up with a debit card issued outside the UK and EEA is free.
- **fee-04** A credit card issued in the UK has a 1.5% top-up fee.
- **fee-05** A credit card issued outside the UK and EEA is charged both the 1.5% credit card fee and the 2.0% fee.
- **fee-06** Topping up with an EEA debit card costs 1.5% of the amount.
- **fee-07** A debit card issued outside the UK and EEA has a 2.0% top-up fee.
- **fee-08** Cash deposits have a fee of 2.0%.
- **fee-09** For a credit card issued outside the UK and EEA, the top-up fee is 2.0%, because only the higher fee is charged.
- **fee-10** Cash deposits have a 1.5% fee.
- **fee-11** Topping up with a UK debit card is free.

## Article `topup-limits`

```
## Card top-up limits
- Minimum per top-up: £10.
- Maximum per top-up: £5,000.
- Maximum per day: £10,000.
- Maximum in any 30 days: £30,000.

## Bank transfer
NovaPay sets no upper limit for bank transfer top-ups. Transfers over £10,000 may need a source of funds check.

## Cash
Each cash deposit must be between £5 and £500.

## Your current allowance
Open **Add money** then **Limits** to see how much of your allowance is left.
```

- **fee-12** Card top-ups are capped at £30,000 in any 30 days.
- **fee-13** The most you can add by card in a single top-up is £10,000.
- **fee-14** Each cash deposit has to be at least £5 and no more than £500.
- **fee-15** Bank transfer top-ups are limited to £10,000.
- **fee-16** You can add up to £10,000 by card in one day.
- **fee-17** The smallest card top-up you can make is £10.
- **fee-18** There is a minimum fee of £10 for topping up by card.
- **fee-19** The card top-up limit is £30,000 per day.

## Article `topup-by-cash`

```
## Cash deposits
You can add cash at a NovaPay Cash Point partner shop. Open **Add money**, choose **Cash**, find a partner shop on the map and show your deposit barcode at the till.

## Amounts and fee
Each deposit must be between £5 and £500. The fee is 1.5% of the amount.

## When it arrives
Most cash deposits appear within 30 minutes. Keep your receipt.

## Cheques
NovaPay does not accept cheques, either by post or by photo. You can pay a cheque into another bank and then send the money to NovaPay by bank transfer.
```

- **fee-20** Adding cash costs a fee of £5.

## Article `cash-withdrawals`

```
## Free allowance
Each calendar month you can withdraw up to £200 in up to 5 withdrawals with no NovaPay fee.

## Fee after the allowance
After either limit is reached, NovaPay charges 2% of the amount, with a minimum fee of £1.

## Daily limit
You can withdraw up to £500 per day.

## Other charges
The cash machine operator may add its own charge. The machine should tell you before you continue. In another currency, the amount is also converted using the exchange rules.
```

- **fee-21** The 2% fee starts only after you have passed both the £200 limit and the 5-withdrawal limit.
- **fee-22** After 5 withdrawals in a month, the NovaPay fee applies to further ones, even if you have taken out less than £200.
- **fee-23** Each calendar month you can withdraw up to £200, in up to 5 withdrawals, with no NovaPay fee.
- **fee-24** After the free allowance, each cash withdrawal costs a flat £1.
- **fee-25** You can withdraw up to £500 a month with no NovaPay fee.
- **fee-26** The daily cash withdrawal limit is £200.
- **fee-27** The daily cash withdrawal limit is £500.
- **fee-28** After the free allowance, a cash withdrawal costs 2% of the amount, and at least £1.

## Article `transfer-fees`

```
## What NovaPay charges
- To another NovaPay user: free.
- UK bank transfer: free.
- SEPA transfer: free.
- International (SWIFT) transfer: £3 per transfer.

The fee is shown before you confirm.

## Charges from other banks
For SWIFT transfers, the receiving bank or a bank in between may deduct its own charge. This can make the amount received lower than the amount sent.

## A fee you did not expect
Open the transfer to see the fee details. If the fee does not match the list above and was not shown before you confirmed, contact support.
```

- **fee-29** Sending money to another NovaPay user is free.
- **fee-30** A SWIFT transfer has a fee of 3% of the amount.
- **fee-31** A SEPA transfer costs £3.
- **fee-32** An international (SWIFT) transfer costs £3.

## Article `exchange-fees`

```
## Weekday allowance
On weekdays you can exchange up to £1,000 per calendar month with no NovaPay exchange fee.

## Above the allowance
Amounts above £1,000 in a month have a 0.5% fee.

## Weekends
From Friday 22:00 to Sunday 22:00 UK time, a 1% weekend markup applies. If you are also above the monthly allowance, both charges apply.

## Before you confirm
The exchange screen shows the rate, the fee and the amount you will receive.
```

- **fee-33** If you exchange more than £1,000 in a month, the 0.5% fee applies to everything you exchanged that month.
- **fee-34** On weekdays you can exchange up to £1,000 per calendar month with no NovaPay exchange fee.
- **fee-35** At the weekend, if you are above your monthly allowance, you pay both the 0.5% fee and the 1% weekend markup.
- **fee-36** At the weekend, if you are above your monthly allowance, only the higher charge, the 1% markup, applies.

## Article `contactless-payments`

```
## Limits
A single contactless payment can be up to £100. After £300 of contactless payments in a row, the card asks for your PIN.

## Contactless is not working
- Make one chip-and-PIN payment first. Contactless on a new card starts after that.
- Check that contactless is switched on under the card's **Security settings**.
- Check that the card is activated and not frozen.
- If one shop's reader fails but others work, the problem is likely the reader.

## Damaged cards
If contactless fails everywhere after these checks, you can order a replacement card.
```

- **fee-37** A single contactless payment can be up to £300.
- **fee-38** A single contactless payment can be up to £100.

## Article `order-physical-card`

```
## How to order
In the app, open **Cards**, choose **Add card**, then **Physical card**. Check the delivery address shown on screen and confirm the order.

## Cost
Your first physical card is free, including standard delivery. Express delivery costs £12.

## How many cards you can have
You can hold up to 2 physical cards on one account. See the spare card article if you want a second one.

## Before it arrives
While you wait, you can create a virtual card in the app and use it for online payments.
```

- **fee-39** Your first physical card is free with standard delivery, and express delivery costs £12.
- **fee-40** Your first physical card costs £5.

## Article `spare-card`

```
## Second physical card
You can order one spare physical card, so that you hold 2 physical cards at most. A spare card costs £5.

Open **Cards**, choose **Add card**, then **Spare physical card**.

## Shared balance
Both cards spend from the same account balance and share the same daily limits. Each card has its own number and PIN.

## Cards for other people
A NovaPay card may only be used by the account holder. Do not give your spare card to someone else.
```

- **fee-41** A spare card costs £12.

## Article `lost-or-stolen-card`

```
## Freeze it now
Open **Cards**, select the card and choose **Freeze**. This stops new payments immediately. If you find the card, choose **Unfreeze**.

## Report it
If you cannot find the card, or you think it was stolen, choose **Report lost or stolen**. This blocks the card permanently. A blocked card cannot be used again, even if you find it.

## Replacement
A replacement card costs £5 with standard delivery.

## Payments you did not make
If you see payments you did not make, contact support straight away. A support agent will review them.
```

- **fee-42** A replacement for a lost or stolen card costs £5 with standard delivery.
