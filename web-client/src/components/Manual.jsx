import { useEffect, useRef } from "react";
import { Z_INDEX } from "../constants/zIndex";
import { useTheme } from "../theme";

/* Player manual. Sections carry stable ids (manual-<key>) so the board can
   deep-link to them: clicking a space opens this with initialSection set to
   that space's section. Content describes the game as implemented (house
   rules included). */

// One entry per section: { key, title, body }. The table of contents and the
// section list are both generated from this, so they never drift apart.
const SECTIONS = [
  {
    key: "objective",
    title: "The Game & How to Win",
    body: (
      <>
        <p>
          Squatter is a race to build the greatest sheep station. You start with
          a small holding and a cash kitty (the host sets the opening kitty,
          $1,000–$3,000; the default is $2,000). Around the board you buy and
          sell stock, improve your pastures, weather droughts and other
          misfortunes, and bank wool cheques.
        </p>
        <p>
          <strong>You win by being the first to a fully stocked, fully
          irrigated station — 30 pens of sheep (6,000 head, at 200 per pen)
          across five irrigated paddocks, with no paddock mortgaged.</strong> A
          player can also win by being the last station still solvent if everyone
          else goes bankrupt.
        </p>
      </>
    ),
  },
  {
    key: "lobby",
    title: "Setting Up & The Lobby",
    body: (
      <>
        <p>
          One player <strong>creates the game</strong> and becomes the host. They
          receive a <strong>6-character game code</strong> — share it (or the
          join link / QR code) so others can join the same game.
        </p>
        <p><strong>Hosting choices (the host sets these in the lobby):</strong></p>
        <ul>
          <li><strong>Number of players</strong> — choose the maximum (2–6). Any
          mix of humans and AI counts toward it.</li>
          <li><strong>Add AI players</strong> — the host can add computer
          opponents, each at a difficulty of <strong>Easy</strong>,
          <strong> Medium</strong> or <strong>Hard</strong>. AI players are run by
          the game automatically and take their turns on their own; you'll see a
          short note of what they're weighing up while they act.</li>
          <li><strong>Opening kitty</strong> — the starting cash each player gets
          ($1,000–$3,000 in $500 steps; default $2,000). Only changeable before
          the game starts.</li>
          <li><strong>AI reaction time</strong> — how long an AI's pop-ups linger
          on screen before it acts (1–10 seconds), so humans can follow along.</li>
        </ul>
        <p>
          <strong>Joining &amp; starting:</strong> human players enter the game
          code and their name to join. Each player marks <strong>Ready</strong>;
          once everyone is ready the host starts the game. All players then roll
          for turn order — highest total goes first, and ties roll again.
        </p>
        <p>
          <strong>Logging out &amp; rejoining:</strong> if you log out, the game is
          <strong> suspended</strong> until you return (AI players don't suspend
          it). To come back, rejoin with the same game code. On the
          <em> same device/browser</em> your session is remembered, so you slip
          straight back in. From a <em>different device</em>, rejoin under your
          original name and enter your personal <strong>rejoin code</strong> — a
          private 6-digit number shown to you in the lobby. (This stops anyone
          else from taking over your station just by knowing your name.) The game
          resumes once every human player is back.
        </p>
      </>
    ),
  },
  {
    key: "turn",
    title: "Taking a Turn",
    body: (
      <>
        <p>
          On your turn you roll the two dice and move that many spaces clockwise,
          then resolve the space you land on. You get <strong>one throw per
          turn</strong> — rolling a double does <em>not</em> earn a second throw.
        </p>
        <p>
          You may manage your station on your own turn (upgrade or mortgage
          paddocks, move sheep between paddocks). Buying and selling stock,
          buying stud rams and haystacks happen when you land on the relevant
          space.
        </p>
      </>
    ),
  },
  {
    key: "wool-sale",
    title: "Wool Sale (Start)",
    body: (
      <>
        <p>
          Every time you <strong>pass or land on Wool Sale</strong> (the Start
          corner) you collect a wool cheque: <strong>$250 per pen of sheep</strong>
          you own, plus <strong>$25 per pen for each stud ram</strong> you hold.
        </p>
        <p>
          Any mortgage interest you owe (see Mortgages) is deducted from the wool
          cheque at the same time.
        </p>
      </>
    ),
  },
  {
    key: "stock-sale",
    title: "Stock Sales",
    body: (
      <>
        <p>
          Stock Sale spaces are where you buy and sell sheep. The catch: you must
          <strong> declare whether you are buying, selling, or passing — and how
          many pens — before the Stock Sale card is turned up.</strong> The card
          then sets the price for that transaction.
        </p>
        <ul>
          <li><strong>Buying:</strong> once you commit, the price is locked. If
          the revealed price means you can't afford the pens you declared, you may
          reduce the count or pass — but you can't increase it or switch to
          selling.</li>
          <li><strong>Selling:</strong> choose how many pens to sell from each
          pasture type. Natural and Improved sell at the card's "natural" price;
          Irrigated at the higher "improved/irrigated" price.</li>
          <li>You may move at most <strong>15 pens</strong> in a single
          transaction.</li>
          <li>A held <strong>High Stock Prices</strong> card adds 20% to your buy
          or sell price (your choice, when you sell or buy).</li>
        </ul>
        <p>You can only buy sheep into empty pen capacity you own (see Pastures).</p>
      </>
    ),
  },
  {
    key: "pastures",
    title: "Pastures & Upgrades",
    body: (
      <>
        <p>You own up to five paddocks. Each paddock has a type and a pen capacity:</p>
        <ul>
          <li><strong>Natural</strong> — 3 pens</li>
          <li><strong>Improved</strong> — 5 pens</li>
          <li><strong>Irrigated</strong> — 6 pens</li>
        </ul>
        <p>
          On your turn you may upgrade a paddock: <strong>Natural → Improved costs
          $500</strong>, and <strong>Improved → Irrigated costs $1,500</strong>.
        </p>
        <p>
          <strong>You must upgrade all five paddocks to Improved before you can
          irrigate any of them.</strong> In other words, no paddock can become
          Irrigated until none of your paddocks are still Natural — then you
          irrigate them one at a time.
        </p>
        <p>
          Irrigated pasture is immune to Local Drought (but exposed to Bore Dries
          Up). The win requires all five paddocks irrigated and fully stocked.
        </p>
      </>
    ),
  },
  {
    key: "stud-rams",
    title: "Stud Rams",
    body: (
      <>
        <p>
          Stud Ram spaces offer a named ram for sale (typically around $500). A
          ram you own:
        </p>
        <ul>
          <li>adds <strong>$25 per pen</strong> to every wool cheque you collect;</li>
          <li>earns you a <strong>stud fee</strong> whenever another player lands
          on that ram's space;</li>
          <li>can be sold back to the bank for <strong>$400</strong>.</li>
        </ul>
        <p>
          The <strong>Stud Ram Dies</strong> space removes the ram with the most
          expensive rent (your highest stud fee). You cannot sell stud rams while
          you are in drought.
        </p>
      </>
    ),
  },
  {
    key: "expenses",
    title: "Expenses",
    body: (
      <>
        <p>
          Many spaces are running costs of the station — shearing, dipping,
          drenching, fencing, vermin and disease control, water drilling, and so
          on. Landing on one charges the listed amount (often per pen of sheep
          you hold). Some carry an immunity card or a bonus:
        </p>
        <ul>
          <li><strong>Drench Sheep for Worms</strong> lets you choose a basic
          treatment or a dearer one that grants the Worm Control Programme card
          (+20% on your next sale).</li>
          <li><strong>Spray for Weeds &amp; Insects</strong> and <strong>Fertilising
          Pasture</strong> grant a +20% next-sale bonus.</li>
          <li><strong>Flood Damage</strong> is a flat $1,000 repair bill.</li>
          <li><strong>Fly Strike Dip / Jet Sheep</strong> clears a pending Blowfly
          Wave penalty before your next wool cheque.</li>
        </ul>
        <p>If you hold the relevant immunity card for a space, you pay nothing.</p>
      </>
    ),
  },
  {
    key: "tucker-bag",
    title: "Tucker Bag Cards",
    body: (
      <>
        <p>
          Landing on a Tucker Bag space draws a card — good or bad. Some are
          one-off events; some can be kept and played later. Effects include:
        </p>
        <ul>
          <li><strong>Income Tax</strong> — pay tax based on your holdings.</li>
          <li><strong>High Stock Prices</strong> — keep it; play for +20% at a
          Stock Sale.</li>
          <li><strong>Local Drought / Drought on ALL Stations</strong> — see Local
          Drought.</li>
          <li><strong>Grass Fire / Fire Destroys Haystack</strong> — lose stock or
          a haystack unless you hold Fire Fighting Equipment; fire destroys
          <em> both</em> haystacks.</li>
          <li><strong>Lucerne Flea / Worm Infestation</strong> — sell off part of
          your flock and suffer a restock block unless protected.</li>
          <li><strong>Blowfly Wave</strong> — your next wool cheque is reduced
          unless you reach a Fly Strike Dip first.</li>
          <li><strong>General Rain / Local Rain</strong> — breaks droughts (see
          Local Rain).</li>
          <li><strong>Sustainable Water Management</strong> — halves the length of
          your next drought or bore restriction.</li>
          <li><strong>Fire Fighting Equipment</strong> — a keepable card that
          protects against fire.</li>
        </ul>
      </>
    ),
  },
  {
    key: "local-drought",
    title: "Local Drought",
    body: (
      <>
        <p>
          When you land on a Local Drought space (or draw a drought card) you must
          <strong> sell half of your Natural and Improved stock</strong> (rounded
          up) to the bank at <strong>$200 per pen</strong> — unless you hold a
          pasture haystack, which lets you sell that stock at full Stock Sale
          prices instead (the haystack is then used up). Irrigated stock is not
          affected.
        </p>
        <p>While in drought you are restricted for one full circuit of the board:</p>
        <ul>
          <li>you may only restock into Irrigated paddocks;</li>
          <li>you cannot upgrade paddocks or sell stud rams.</li>
        </ul>
        <p>
          <strong>House rule — no extension:</strong> a drought lasts exactly one
          circuit from where it began. Landing on Local Drought again, or drawing
          another drought card, while you are already in drought has <em>no
          effect</em> and does not extend it. Once you complete the circuit the
          drought ends; only a fresh landing after that starts a new one.
          <strong> Drought on ALL Stations</strong> applies a fresh drought to
          every player not already in one.
        </p>
      </>
    ),
  },
  {
    key: "bore-dries-up",
    title: "Bore Dries Up",
    body: (
      <>
        <p>
          Bore Dries Up is the irrigated counterpart of drought. If you own
          Irrigated pasture you must <strong>sell half of your Irrigated stock</strong>
          (rounded up) at <strong>$300 per pen</strong> — or <strong>$500 per
          pen</strong> if you hold an irrigated haystack (used up in the process).
          A player with no Irrigated pasture is unaffected.
        </p>
        <p>
          Afterwards you cannot restock Irrigated paddocks for one full circuit
          (Natural and Improved restocking is still allowed). As with drought,
          this period is <strong>never extended</strong> — landing on Bore Dries
          Up again while still restricted has no effect.
        </p>
      </>
    ),
  },
  {
    key: "haystacks",
    title: "Haystacks",
    body: (
      <>
        <p>
          Haystacks are drought insurance, bought during the <strong>Haymaking
          Season</strong> strip of the board. There are two kinds, each matched to
          a hazard:
        </p>
        <ul>
          <li><strong>Pasture haystack</strong> — softens a <em>Local Drought</em>
          (lets you sell Natural/Improved stock at Stock Sale prices instead of
          $200/pen).</li>
          <li><strong>Irrigated haystack</strong> — softens a <em>Bore Dries
          Up</em> ($500/pen instead of $300/pen).</li>
        </ul>
        <p>
          You may hold one of each, but you are only offered the kind your station
          can actually use (you need Natural/Improved pasture for a pasture
          haystack, Irrigated for an irrigated one). A haystack costs
          <strong> $500</strong>, rising to <strong>$1,000</strong> only while the
          matching hazard is currently affecting you. A haystack is consumed when
          it offsets its hazard, and you can sell an unwanted one back for
          <strong> $350</strong> (handy if you upgrade all your pasture to
          Irrigated and no longer need the pasture haystack). A fire destroys both
          haystacks.
        </p>
      </>
    ),
  },
  {
    key: "local-rain",
    title: "Local Rain & General Rain",
    body: (
      <p>
        <strong>Local Rain</strong> breaks a drought (or bore restriction) on your
        own station if you are affected. <strong>General Rain</strong> (a Tucker
        Bag card) breaks the drought on <em>every</em> station at once. A broken
        drought ends immediately — the restrictions lift.
      </p>
    ),
  },
  {
    key: "mortgages",
    title: "Mortgages",
    body: (
      <>
        <p>
          When you are short of cash you may mortgage paddocks to the bank — but
          <strong> only once you have been reduced to 8 pens of sheep or
          fewer</strong>. Mortgage values are <strong>$100</strong> (Natural),
          <strong> $250</strong> (Improved) and <strong>$750</strong> (Irrigated).
        </p>
        <p>
          A mortgaged paddock holds no sheep and earns nothing. You pay
          <strong> 10% interest</strong> on your mortgages out of each wool cheque.
          To lift a mortgage you repay the value plus 10% (e.g. $110 for a Natural
          paddock). You cannot win while any paddock is mortgaged.
        </p>
      </>
    ),
  },
  {
    key: "visiting-town",
    title: "Visiting Town",
    body: (
      <p>
        Landing on a Visiting Town space costs you time, not money: you
        <strong> miss your next two turns</strong> while you're away from the
        station.
      </p>
    ),
  },
  {
    key: "debt",
    title: "Debt & Bankruptcy",
    body: (
      <>
        <p>
          Forced payments (expenses, mortgage interest, card effects) can push
          your cash below zero. When that happens, <strong>play halts until you
          settle the debt</strong> — you (and everyone else) cannot roll until you
          are back to $0 or better. Raise the money by selling sheep to the bank
          at the emergency price of <strong>$400 per pen</strong>, mortgaging
          paddocks, or selling stud rams and haystacks. The debt banner offers a
          one-click emergency sale of just enough sheep.
        </p>
        <p>
          If your debt is larger than everything you could possibly raise by
          selling up, your station is <strong>bankrupt</strong> and you retire
          from the game. When only one solvent station remains, that player wins.
        </p>
      </>
    ),
  },
];

export default function Manual({ onClose, initialSection }) {
  const { theme } = useTheme();
  const scrollRef = useRef(null);

  // Deep-link: scroll the requested section into view when opened.
  useEffect(() => {
    if (!initialSection) return;
    const el = document.getElementById(`manual-${initialSection}`);
    if (el) {
      // Defer so the modal has laid out before we scroll within it.
      requestAnimationFrame(() => el.scrollIntoView({ block: "start" }));
    }
  }, [initialSection]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const goTo = (key) => {
    document.getElementById(`manual-${key}`)?.scrollIntoView({ block: "start", behavior: "smooth" });
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: Z_INDEX.POPUP_CARD_DETAILS,
      }}
    >
      <div
        ref={scrollRef}
        onClick={(e) => e.stopPropagation()}
        style={{
          background: theme.modalBg, color: theme.modalText,
          borderRadius: 12, width: "min(760px, 92vw)", maxHeight: "88vh",
          overflowY: "auto", boxShadow: `0 12px 48px ${theme.modalShadow}`,
          position: "relative",
        }}
      >
        <div style={{
          position: "sticky", top: 0, background: "#2d5016", color: "#fff",
          padding: "1rem 1.4rem", display: "flex", justifyContent: "space-between",
          alignItems: "center", borderTopLeftRadius: 12, borderTopRightRadius: 12,
        }}>
          <h1 style={{ margin: 0, fontSize: "1.4rem", fontFamily: "'Georgia', serif" }}>
            Squatter — Player Manual
          </h1>
          <button onClick={onClose} aria-label="Close" style={{
            background: "rgba(255,255,255,0.2)", border: "none", color: "#fff",
            fontSize: "1.2rem", borderRadius: 6, cursor: "pointer", padding: "2px 10px",
          }}>×</button>
        </div>

        <div style={{ padding: "1.2rem 1.4rem" }}>
          {/* Contents */}
          <div style={{
            marginBottom: "1.2rem", padding: "0.8rem 1rem", borderRadius: 8,
            background: theme.panelBg, border: `1px solid ${theme.panelBorder}`,
          }}>
            <strong style={{ display: "block", marginBottom: "0.4rem" }}>Contents</strong>
            <ol style={{ margin: 0, paddingLeft: "1.2rem", columns: 2, fontSize: "0.9rem" }}>
              {SECTIONS.map((s) => (
                <li key={s.key} style={{ marginBottom: 3 }}>
                  <button onClick={() => goTo(s.key)} style={{
                    background: "none", border: "none", padding: 0, cursor: "pointer",
                    color: "#1565a0", textDecoration: "underline", font: "inherit", textAlign: "left",
                  }}>{s.title}</button>
                </li>
              ))}
            </ol>
          </div>

          {/* Sections */}
          {SECTIONS.map((s) => (
            <section key={s.key} id={`manual-${s.key}`} style={{ scrollMarginTop: 64, marginBottom: "1.4rem" }}>
              <h2 style={{
                fontSize: "1.15rem", color: "#2d5016", borderBottom: `2px solid ${theme.panelBorder}`,
                paddingBottom: 4, marginBottom: "0.5rem",
              }}>{s.title}</h2>
              <div style={{ fontSize: "0.92rem", lineHeight: 1.5 }}>{s.body}</div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
