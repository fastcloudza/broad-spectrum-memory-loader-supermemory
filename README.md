# Broad Spectrum Conversation Memory Loader

Loads one customer's conversations from several channels (a phone call, a chat, a
voice note, a meeting, a document) into [Supermemory](https://supermemory.ai) as
speaker-attributed text, one namespace per customer. Then it shows what Supermemory
learned: the customer's profile, and memories that link facts across channels.

## Why

A business talks to a customer over calls, chats, voice notes and documents. If each
one is reduced to the same shape, text attributed to the customer or to the agent,
they can all go into one memory. The memory can then connect a fact from a call with
a fact from a chat.

## Quickstart

You need Python 3.10 or later and a Supermemory API key.

```bash
git clone <repository-url> broad-spectrum-conversation-memory-loader
cd broad-spectrum-conversation-memory-loader
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .

cp .env.example .env          # then put your key in SUPERMEMORY_API_KEY

conversation-memory-loader load --instant      # send the six sample threads
conversation-memory-loader show cust_001       # profile and searches for the first customer
```

`load --dry-run` prints what would be sent and needs no key.

`show` waits until every thread has been processed and has formed memories. On a
fresh load this took a few minutes. `--instant` makes Supermemory process each
thread straight away, which it bills as one extra operation per thread.

To start again from nothing, `conversation-memory-loader reset cust_001 cust_002 --yes`
permanently deletes both customers' namespaces.

## The sample data

Everything in `sample_data/` is invented: a fictional installer, Fernhollow Solar,
and two fictional customers.

| Customer | Threads |
|---|---|
| `cust_001` | a phone call, a document (an electricity statement), a chat, a voice note |
| `cust_002` | a chat that contains a voice note, a meeting |

The first customer's threads only make sense together. In the call she mentions, in
passing, that she is not home before one, that an electric car is arriving in
November, and that the first quote is for a 5 kWh battery. The later chat asks
whether the battery is "big enough once the car arrives" and for the crew to come
"at the usual time", without restating either fact. The statement holds her
night-rate hours, and a voice note moves the installation by a day. So `show
cust_001` asks questions such as:

- *Why is the battery bigger than the one first quoted?* The first quote and the car
  are in the call; the upgrade and its price are in the chat.
- *What time of day should the installation crew arrive, and why?* The time is in
  the chat, the reason is in the call, and the change of day is in the voice note.

The questions live in `sample_data/questions.json`.

## Sample output

`conversation-memory-loader load --dry-run` prints one payload per thread. This is the
voice note:

```json
{
  "namespace": "conv_cust_001",
  "id": "thread_0004",
  "content": "[voice note]\ncustomer: Hi Ansel, it's Marisol. Two quick things for the installation. First, the side gate is too narrow for the battery, so the crew will need to bring it through the garage. I'll leave the garage door open for them. Second, my rota has changed, so could we move the installation from Thursday 15 October to Friday 16 October, same time? Thanks.",
  "metadata": {
    "source": "broad-spectrum-conversation-memory-loader",
    "channel": "voice_note",
    "turn_count": 1
  },
  "date": "2026-10-06T17:40:00+01:00",
  "dreaming": "dynamic",
  "supporting_context": "These are conversations between a business's agents and one customer, across several channels: chats, phone calls, voice notes, meetings and documents. Lines starting with 'agent:' are the business speaking; lines starting with 'customer:' are the customer."
}
```

Below is a real run of `conversation-memory-loader show cust_001`, unedited, from
12 October 2026. Each search returns at most five results. The number on the left is
Supermemory's relevance score, from 0 to 1: how close a result is in meaning to the
question, not how likely it is to be correct. The results at the top with scores
near 1 are answers Supermemory wrote by combining several memories (see
[Searches](#searches)). Results marked `source:` are passages of the original
transcripts, shortened here to one line.

What to look at:

- **Memories from every channel.** The call, the statement, the chat and the voice
  note each produced memories, and the profile combines them.
- **Facts joined across channels.** For the battery question, the 0.72 answer takes
  the first quote and the car from the call and the upgrade and price from the chat.
  For the delivery question, it takes the garage route and the new day from the
  voice note and the time from the chat.
- **What it got wrong.** The 0.90 answer to the battery question is wrong: it cites
  the fuse rating and the old Thursday date. The last profile entry, a summary
  Supermemory wrote, says "$1,900" and "Friday 15 October" and adds a preference
  nobody stated. One memory has the reminder going "to Ansel", who is the agent.
  The crew-arrival answer gives a reason ("easier if they arrive later in the day")
  that is not in the conversations.

The combined answers are generated each time, so a new run gives different wording.

<details>
<summary>Full output</summary>

```text
Customer cust_001  (namespace conv_cust_001)
Documents: 4
  thread_0001  done
  thread_0002  done
  thread_0003  done
  thread_0004  done

Memories: 29
  thread_0001  10
  thread_0002  11
  thread_0003  5
  thread_0004  3

Profile
  Static
    - M. Venn (Marisol Venn) is a member of Quillhaven Power Co-operative.
  Dynamic
    - [2026-09-14] Marisol works an early shift at Dunmere Bakery and is not home until about 1 PM.
    - [2026-09-14] Marisol will receive an electric car from her sister in November.
    - [2026-09-14] Marisol wants advance warning before anyone visits because her dog Biscuit is nervous around strangers.
    - [2026-09-14] Marisol will receive the quote by Wednesday 16 September 2026.
    - [2026-09-14] The starting quote includes a 4 kilowatt solar array and a 5 kilowatt‑hour battery.
    - [2026-09-14] Marisol Venn is a customer of Fernhollow Solar.
    - [2026-09-14] Marisol has requested a quote for solar panels and a battery for her house in Quillhaven.
    - [2026-09-14] Marisol's roof is a back roof over the garden with slate tiles, redone two years ago, and is in good shape.
    - [2026-09-14] Marisol will send her electricity usage statement later that week.
    - [2026-09-14] Marisol prefers to be contacted only in the afternoons, not before 1 PM.
    - [2026-09-22] Quote updated to a 4 kW array and a 10 kWh battery.
    - [2026-09-22] The 10 kWh battery costs £1,900 more than the previous option.
    - [2026-09-22] Installation scheduled for Thursday 15 October 2026.
    - [2026-09-22] Crew will arrive at 1:30 pm on Thursday 15 October 2026.
    - [2026-09-22] Agent will send a reminder to Ansel on 14 October 2026 regarding the installation on 15 October 2026.
    - [2026-10-06] Marisol will leave the garage door open for the installation crew during the battery installation.
    - [2026-10-06] Installation scheduled for Friday 16 October instead of Thursday 15 October, same time.
    - [2026-10-06] Side gate too narrow for battery; installation crew must bring battery through the garage.
    - [2026-09-17] Quillhaven Power Co-operative supplies electricity under a Night Owl two-rate tariff to member M. Venn.
    - [2026-09-17] Statement period for M. Venn electricity usage: 1 September 2025 to 31 August 2026.
    - [2026-09-17] Night Owl two-rate tariff: night rate 9 pence per kWh from 00:30 to 05:30 daily, day rate 31 pence per kWh at all other times.
    - [2026-09-17] Total consumption during the statement period: 3,150 kWh.
    - [2026-09-17] Night rate consumption: 410 kWh.
    - [2026-09-17] Day rate consumption: 2,740 kWh.
    - [2026-09-17] Supply type for M. Venn: single phase.
    - [2026-09-17] Main fuse rating for M. Venn's supply: 80 amps.
    - [2026-09-17] M. Venn does not have an export meter fitted.
    - [2026-09-17] M. Venn shared the electricity statement with Fernhollow Solar.
    - Home‑solar project and customer preferences: Marisol Venn owns a home with a slate roof that was redone two years ago and is currently in good condition. She is a member of QUILLHAVEN POWER CO‑OPERATIVE, which provides a single‑phase supply with an 80‑amp main fuse and uses the Night Owl two‑rate tariff (day rate 31 pence/kWh, night rate 9 pence/kWh, night period 00:30–05:30). During the statement period 1 September 2025–31 August 2026, her consumption was 3,150 kWh (2,740 kWh day, 410 kWh night). Marisol will receive an electric car in November 2026, increasing her power demand. She prefers afternoon calls only after 1 pm, wants advance warning before visits because her nervous dog Biscuit reacts to strangers, and prefers to move visits if necessary. She has requested a 4 kW solar array with a 10 kWh battery (the battery costs $1,900 more than the previous model). The installation is scheduled for Friday 15 October 2026 at 1:30 pm, with the crew arriving at 1:30 pm, the garage door left open, and the battery delivered through the garage because the side gate is too narrow.

Q: When is the cheapest time for this customer to charge her car?
    1.00  The customer is on the Night Owl two‑rate tariff supplied by Quillhaven Power Co‑operative. Night rate (00:30–05:30) is 9 pence/kWh and day rate is 31 pence/kWh, so the cheapest time to charge the car is any period within the nightly window.
    0.95  Over the 12‑month statement period (1 Sep 2025–31 Aug 2026) the customer consumed 3,150 kWh total, of which 410 kWh were at night rate and 2,740 kWh at day rate.
    0.90  The tariff structure and consumption split confirm that the majority of usage falls outside night hours, but the nightly period remains the lowest cost interval for charging.
    0.71  Night Owl two-rate tariff: night rate 9 pence per kWh from 00:30 to 05:30 daily, day rate 31 pence per kWh at all other times.
    0.69  source: [document] customer: Annual electricity statement issued by Quillhaven Power Co-operative, the electricity supplier, to its member M. Venn (Marisol Venn), wh...

Q: What time of day should the installation crew arrive, and why?
    0.99  The crew should arrive at 1:30 pm on the scheduled installation day. Marisol has indicated that she is only available after 1 pm and prefers to be contacted in the afternoons. Additionally, the side gate is too narrow for the battery, so the crew will bring it through the garage—an arrangement that is easier if they arrive later in the day. The installation was originally set for Thursday 15 October, but Marisol requested a shift to Friday 16 October; in either case, the crew’s arrival time remains 1:30 pm.
    0.67  Marisol will leave the garage door open for the installation crew during the battery installation.
    0.67  Installation scheduled for Friday 16 October instead of Thursday 15 October, same time.
    0.66  Crew will arrive at 1:30 pm on Thursday 15 October 2026.
    0.64  source: [voice note] customer: Hi Ansel, it's Marisol. Two quick things for the installation. First, the side gate is too narrow for the battery, so the crew will ne...

Q: Why is the battery bigger than the one first quoted?
    0.90  Installation scheduled for Thursday 15 October 2026, with Marisol leaving the garage door open for the battery installation crew. The quote was received on Wednesday 16 September 2026. The main fuse rating for M. Venn's supply is 80 amps, which will support the larger battery being installed.
    0.73  source: [chat] customer: Hi Ansel, I got the quote, thank you. Will that battery still be big enough once the car arrives? agent: Good question. On its own, probably...
    0.72  The customer’s initial quote included a 5 kWh battery, but after learning she would be receiving an electric car in November, the agent upgraded the proposal to a 10 kWh battery. The larger battery was chosen because the customer’s future increased electricity demand would likely exceed the capacity of the smaller unit. The agent explained that the 10 kWh option costs £1,900 more than the 5 kWh alternative and that the quote was updated to a 4 kW solar array plus the larger battery.
    0.70  The 10 kWh battery costs £1,900 more than the previous option.
    0.70  The agent’s final quote reflects the larger battery: a 4 kW array and a 10 kWh battery, which is the version that the customer chose after the upgrade. This updated quote supersedes the earlier 5 kWh proposal and includes the additional cost and battery size change.

Q: How should the crew bring the battery to the house, and on which day?
    0.76  The crew must bring the battery through the garage because the side gate is too narrow. Marisol has agreed to leave the garage door open for the installation crew.
    0.76  Marisol will leave the garage door open for the installation crew during the battery installation.
    0.73  The installation is scheduled for Friday 16 October 2026, with the crew arriving at 1:30 pm. This date was moved from the originally planned Thursday 15 October at the same time.
    0.73  Side gate too narrow for battery; installation crew must bring battery through the garage.
    0.69  source: [voice note] customer: Hi Ansel, it's Marisol. Two quick things for the installation. First, the side gate is too narrow for the battery, so the crew will ne...
```

</details>

## Input format

One JSON file per conversation thread, anywhere under the folder you pass to `load`:

```json
{
  "customer_id": "cust_001",
  "thread_id": "thread_0007",
  "channel": "phone_call",
  "started_at": "2026-09-14T09:12:00+02:00",
  "turns": [
    {"speaker": "customer", "text": "..."},
    {"speaker": "agent", "text": "..."}
  ]
}
```

- `channel` is one of `chat`, `phone_call`, `voice_note`, `meeting`, `document`.
- `speaker` is `customer` or `agent`.
- A document is a single `customer` turn holding the extracted text.
- A turn may carry its own `channel`, which overrides the thread's. Use this for a
  chat that contains a voice note, for example.
- Turns with no text are skipped. Line breaks inside a turn become spaces, so a turn
  is always one line.

## What is sent to Supermemory

One thread is one document.

| Field | Value |
|---|---|
| namespace | `conv_<customer_id>`, or `conv_<HMAC>` (see below) |
| id | the `thread_id`. Reusing an id appends, so running `load` twice is safe |
| content | the channel in square brackets, then one `customer: ...` or `agent: ...` line per turn. When a thread mixes channels, the channel is on every line instead |
| metadata | `source`, `channel`, `turn_count` (flat values only) |
| date | `started_at`, so a thread sits at the point in time it happened |
| supporting context | two sentences saying who the speakers are |
| dreaming | `dynamic`, or `instant` with `--instant` |

## Searches

`show` waits until every document in the customer's namespace is `done` and has
formed memories, then prints the document and memory counts, the profile (static
and dynamic), and the results of each question.

Each question is a hybrid search (learned memories plus passages of the original
transcripts) with Supermemory's `aggregate` rerank, which combines overlapping
results into written answers. A plain memory search returns the facts closest to
the question one at a time, so a question that needs a fact from a call and another
from a chat usually got only one of them. Related memories are included when
Supermemory returns them.

## Namespaces and `NAMESPACE_SECRET`

By default the namespace is `conv_` followed by the customer id. That is fine for
opaque ids such as `cust_001`.

Set `NAMESPACE_SECRET` whenever the customer id is a phone number, an email address
or anything else guessable. The namespace then becomes `conv_` followed by an
HMAC-SHA256 of the customer id with that secret, so the id itself is not sent as an
identifier. Keep the secret the same between runs, or the same customer will land in
a different namespace. Note that this covers the namespace only: whatever is in the
conversation text is still sent.

## Using your own data

1. Write one JSON file per thread in the format above. Transcribe audio and extract
   document text first; this tool only handles text.
2. Run `conversation-memory-loader load path/to/your/folder --dry-run` and read the payloads.
3. Run it again without `--dry-run`.
4. Ask your own questions:
   `conversation-memory-loader show <customer_id> -q "..." -q "..."`,
   or point `--questions` at a JSON file that maps customer ids to lists of questions.

## Commands

```text
conversation-memory-loader load [FOLDER] [--dry-run] [--instant]
conversation-memory-loader show CUSTOMER_ID [-q QUESTION]... [--questions FILE] [--limit N] [--timeout SECONDS]
conversation-memory-loader reset CUSTOMER_ID... --yes
```

`reset` permanently deletes each customer's namespace, with its documents and
memories. It does nothing without `--yes`.

`FOLDER` defaults to `sample_data/threads` and `--questions` to
`sample_data/questions.json`, both relative to the current directory.

## Layout

```text
src/conversation_memory_loader/
  threads.py     read and validate thread files, format transcripts
  namespace.py   derive the namespace for a customer
  memory.py      every Supermemory call; the one place to change for another back end
  cli.py         the load, show and reset commands
sample_data/     six synthetic threads and the demo questions
tests/           unit tests; none of them use the network
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Licence

MIT. See [LICENSE](LICENSE).
