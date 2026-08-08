export type FaqEntry = {
  id: string
  question: string
  answer: string
  keywords: string[]
}

export const faq: FaqEntry[] = [
  {
    id: 'un-une',
    question: 'When do I use "un" vs "une"?',
    answer:
      'Every French noun is masculine (un) or feminine (une), and it\'s mostly arbitrary — so the safest habit is to always learn the article WITH the noun ("une pomme", not just "pomme"). A few patterns help: nouns ending in -tion, -sion, -té, or -ette are almost always feminine (une addition, une université). Nouns ending in -age, -ment, -eau, or -isme are usually masculine (un fromage, un moment). Endings in -e are often feminine (une chaise) but have plenty of exceptions (un problème). When unsure, guess and get corrected — that\'s normal, even for natives with tricky words.',
    keywords: [
      'un', 'une', 'gender', 'masculine', 'feminine', 'article',
      'un ou une', 'un vs une', 'un et une', 'un/une',
    ],
  },
  {
    id: 'le-la',
    question: 'What\'s the difference between "le" and "la"?',
    answer:
      '"Le" and "la" are the definite articles ("the") — "le" for masculine nouns, "la" for feminine ones, and both shorten to "l\'" before a vowel sound (l\'arrêt, l\'horaire). Same rule of thumb as un/une: the gender is tied to the noun, so learn them as a pair.',
    keywords: ['le', 'la', 'l\'', 'the', 'definite article'],
  },
  {
    id: 'vous-tu',
    question: 'When should I use "tu" instead of "vous"?',
    answer:
      'In Geneva, almost never in transactional settings — shops, transport, strangers, service staff all get "vous". "Tu" is reserved for close friends, family, children, or once someone explicitly invites you to switch ("On peut se tutoyer ?"). If you\'re not sure, "vous" is always the safe default.',
    keywords: ['tu', 'vous', 'tutoyer', 'vouvoyer', 'formal', 'informal'],
  },
  {
    id: 'sil-vous-plait-te',
    question: 'Why is it "s\'il vous plaît" and not "s\'il te plaît"?',
    answer:
      '"S\'il vous plaît" literally means "if it pleases you" using the formal "vous". "S\'il te plaît" is the same phrase with informal "tu". Since Geneva defaults to "vous" with strangers, stick with "s\'il vous plaît" in shops, transport, and any transaction.',
    keywords: ['s\'il vous plaît', 's\'il te plaît', 'please', 'svp'],
  },
  {
    id: 'bonjour-bonsoir',
    question: 'When do I switch from "bonjour" to "bonsoir"?',
    answer:
      'There\'s no strict clock time — it\'s about daylight and local habit. "Bonjour" covers morning through late afternoon; people typically switch to "bonsoir" around early evening (roughly 6–7pm) as it gets dark. When in doubt, listen to what the person greeting you says and mirror it.',
    keywords: ['bonjour', 'bonsoir', 'morning', 'evening', 'greeting', 'time of day'],
  },
  {
    id: 'merci-beaucoup',
    question: 'Is "merci beaucoup" more polite than "merci"?',
    answer:
      '"Merci" alone is perfectly polite for everyday transactions (buying something, small favors). "Merci beaucoup" ("thanks a lot") adds warmth or emphasis — use it when someone goes out of their way to help you, gives directions, or does something extra.',
    keywords: ['merci', 'merci beaucoup', 'thank you', 'thanks'],
  },
  {
    id: 'je-voudrais-veux',
    question: 'What\'s the difference between "je voudrais" and "je veux"?',
    answer:
      '"Je veux" ("I want") is blunt and can sound demanding. "Je voudrais" ("I would like") is the conditional form and reads as softer and more polite — it\'s the standard way to order or ask for something in a shop, café, or restaurant. Default to "je voudrais" whenever you\'re requesting something from someone.',
    keywords: ['je voudrais', 'je veux', 'want', 'would like', 'ordering'],
  },
  {
    id: 'swiss-numbers',
    question: 'Why do Swiss French numbers look different (septante, nonante)?',
    answer:
      'France counts 70/80/90 awkwardly as "60+10", "4×20", "4×20+10" (soixante-dix, quatre-vingts, quatre-vingt-dix). Switzerland simplifies 70 and 90 to "septante" and "nonante". 80 is the exception: some Swiss regions say "huitante", but Geneva often still uses the French "quatre-vingts" — so listen for both.',
    keywords: [
      'septante', 'nonante', 'huitante', 'octante', 'quatre-vingts',
      'numbers', 'swiss numbers', '70', '80', '90',
    ],
  },
  {
    id: 'combien-quel',
    question: 'What\'s the difference between "combien" and "quel"?',
    answer:
      '"Combien" asks "how much / how many" — it\'s about quantity ("C\'est combien ?" = "How much is it?"). "Quel/quelle" asks "which" — it\'s about picking an option ("Quelle ligne ?" = "Which line?"). If you\'re asking about a number or price, use combien; if you\'re choosing between options, use quel.',
    keywords: ['combien', 'quel', 'quelle', 'how much', 'which', 'price'],
  },
  {
    id: 'cest-il-est',
    question: 'When do I use "c\'est" vs "il est" / "elle est"?',
    answer:
      '"C\'est" is used before a noun or name ("C\'est le tram 15", "C\'est loin"). "Il est / elle est" is used before an adjective describing a specific person or thing already mentioned ("Il est gentil"). As a beginner, "c\'est" is the safer default for most descriptions and identifications.',
    keywords: ['c\'est', 'il est', 'elle est', 'ces vs il est'],
  },
  {
    id: 'ou-quand',
    question: 'What\'s the difference between "où" and "quand"?',
    answer:
      '"Où" means "where" (a place) — "Où est l\'arrêt ?" = "Where is the stop?". "Quand" means "when" (a time) — "Quand part le bus ?" = "When does the bus leave?". Easy to mix up when speaking fast, so it helps to pair each with a mental picture: où → a pin on a map, quand → a clock.',
    keywords: ['où', 'quand', 'where', 'when'],
  },
  {
    id: 'a-de',
    question: 'When do I use "à" vs "de"?',
    answer:
      '"À" generally points toward a destination, location, or time ("à Genève", "à 8 heures", "un billet à Cornavin" for going there). "De" points away from an origin or shows possession/material ("venir de Genève", "la carte de transport"). If you\'re describing motion or direction toward something, reach for "à"; for origin or "of", reach for "de".',
    keywords: ['à', 'de', 'a vs de', 'preposition'],
  },
  {
    id: 'billet-carte',
    question: 'What\'s the difference between "un billet" and "une carte"?',
    answer:
      '"Un billet" is a single-use ticket bought for one trip. "Une carte" (or "un abonnement") is a pass or subscription covering many trips over time — like a weekly or monthly TPG pass. If you\'re only riding once, ask for "un billet"; for regular use, ask about "un abonnement".',
    keywords: ['billet', 'carte', 'abonnement', 'ticket', 'pass'],
  },
  {
    id: 'excusez-moi-pardon',
    question: 'When do I say "excusez-moi" vs "pardon"?',
    answer:
      '"Excusez-moi" is used to get someone\'s attention or interrupt politely (asking directions, squeezing past on a tram). "Pardon" is more for a quick apology after a minor bump or mistake. In practice they overlap a lot — both are safe, polite choices.',
    keywords: ['excusez-moi', 'pardon', 'excuse me', 'sorry'],
  },
  {
    id: 'descendre-monter',
    question: 'What\'s the difference between "descendre" and "monter"?',
    answer:
      '"Descendre" means to get off / go down ("Je descends" = "I\'m getting off"). "Monter" means to get on / go up ("Je monte" = "I\'m getting on"). On the tram, you\'ll mostly need "je descends" to signal you want off at the next stop.',
    keywords: ['descendre', 'monter', 'descends', 'monte', 'get off', 'get on'],
  },
  {
    id: 'voila-meaning',
    question: 'What does "voilà" actually mean?',
    answer:
      '"Voilà" is an all-purpose word meaning roughly "there it is / here you go / that\'s it". Shopkeepers say it while handing you your item or change; you can also use it yourself when handing something over, or to wrap up a thought ("Voilà, c\'est tout").',
    keywords: ['voilà', 'voila', 'here you go', 'there it is'],
  },
  {
    id: 'tout-droit-a-droite',
    question: 'What\'s the difference between "tout droit" and "à droite"?',
    answer:
      '"Tout droit" means "straight ahead" (keep going forward). "À droite" means "to the right" (turn right). They sound similar but mean opposite things for navigation — mixing them up is a classic beginner mistake, so it\'s worth drilling them as a pair.',
    keywords: ['tout droit', 'à droite', 'à gauche', 'straight', 'right', 'left', 'directions'],
  },
  {
    id: 'comment-allez-vous-ca-va',
    question: '"Comment allez-vous ?" vs "Ça va ?" — what\'s the difference?',
    answer:
      '"Comment allez-vous ?" is the full, formal way to ask "How are you?" and pairs with "vous". "Ça va ?" is a casual shortcut used with people you know or in relaxed settings, and the reply is often just "Ça va" (I\'m fine / it\'s going okay). For strangers and transactions, stick with "Comment allez-vous ?".',
    keywords: ['comment allez-vous', 'ça va', 'how are you'],
  },
]
