export type Phrase = {
  fr: string
  en: string
  note?: string
}

export type DialogueLine = {
  speaker: string
  fr: string
  en: string
}

export type UseCase = {
  phrase: string
  use: string
}

export type NumberEntry = {
  n: number
  fr: string
  swissTwist?: string
}

export type Session = {
  id: number
  title: string
  subtitle: string
  kind: 'phrases' | 'numbers' | 'transaction' | 'roleplay'
  corePhrases?: Phrase[]
  grammarSeed?: string
  dialogue?: DialogueLine[]
  drill: string
  numbers?: NumberEntry[]
  numbersUseCase?: string
  useCases?: UseCase[]
  roleplaySteps?: { title: string; hint: string }[]
}

export type VocabItem = {
  fr: string
  en: string
}

export type Week = {
  id: number
  title: string
  goal: string
  sessions: Session[]
  vocab: VocabItem[]
}

const numbers: NumberEntry[] = [
  { n: 0, fr: 'zéro' },
  { n: 1, fr: 'un' },
  { n: 2, fr: 'deux' },
  { n: 3, fr: 'trois' },
  { n: 4, fr: 'quatre' },
  { n: 5, fr: 'cinq' },
  { n: 6, fr: 'six' },
  { n: 7, fr: 'sept' },
  { n: 8, fr: 'huit' },
  { n: 9, fr: 'neuf' },
  { n: 10, fr: 'dix' },
  { n: 11, fr: 'onze' },
  { n: 12, fr: 'douze' },
  { n: 13, fr: 'treize' },
  { n: 14, fr: 'quatorze' },
  { n: 15, fr: 'quinze' },
  { n: 16, fr: 'seize' },
  { n: 17, fr: 'dix-sept' },
  { n: 18, fr: 'dix-huit' },
  { n: 19, fr: 'dix-neuf' },
  { n: 20, fr: 'vingt' },
  { n: 30, fr: 'trente' },
  { n: 40, fr: 'quarante' },
  { n: 50, fr: 'cinquante' },
  { n: 60, fr: 'soixante' },
  {
    n: 70,
    fr: 'septante',
    swissTwist:
      'France says "soixante-dix" (60+10). Swiss French always says septante — much simpler.',
  },
  {
    n: 80,
    fr: 'huitante',
    swissTwist:
      'Some Swiss regions say "huitante" or "octante", but Geneva often still uses the French "quatre-vingts" (4×20). Listen for both.',
  },
  {
    n: 90,
    fr: 'nonante',
    swissTwist:
      'France says "quatre-vingt-dix" (4×20+10). Swiss French always says nonante — the single biggest trap for France-focused apps.',
  },
  { n: 100, fr: 'cent' },
]

export const week1: Week = {
  id: 1,
  title: 'Week 1: Foundations',
  goal:
    'Survive a 30-second transactional exchange (greeting → request → thanks → goodbye) without freezing.',
  sessions: [
    {
      id: 1,
      title: 'Bonjour to Au revoir',
      subtitle: 'Greetings & courtesy',
      kind: 'phrases',
      corePhrases: [
        { fr: 'Bonjour', en: 'Hello / Good day' },
        { fr: 'Bonsoir', en: 'Good evening' },
        { fr: "Je m'appelle…", en: 'My name is…' },
        { fr: 'Comment allez-vous ?', en: 'How are you?' },
        { fr: 'Très bien, merci', en: 'Very well, thank you' },
        { fr: "S'il vous plaît", en: 'Please' },
        { fr: 'Merci', en: 'Thank you' },
        { fr: 'De rien', en: "You're welcome" },
        { fr: 'Au revoir', en: 'Goodbye' },
        { fr: 'Bonne journée', en: 'Have a good day' },
      ],
      grammarSeed:
        '"Vous" is the Swiss social default — skip "tu" entirely for now; you\'ll almost never need it in Geneva transactional settings.',
      dialogue: [
        { speaker: 'A', fr: 'Bonjour Madame.', en: 'Hello Madam.' },
        {
          speaker: 'B',
          fr: 'Bonjour Monsieur, comment allez-vous ?',
          en: 'Hello Sir, how are you?',
        },
        {
          speaker: 'A',
          fr: 'Très bien, merci, et vous ?',
          en: 'Very well, thank you, and you?',
        },
        { speaker: 'B', fr: 'Ça va bien, merci.', en: "I'm doing well, thanks." },
      ],
      drill: 'Say it out loud 5x, varying the time of day (bonjour / bonsoir).',
    },
    {
      id: 2,
      title: 'Numbers & the Swiss twist',
      subtitle: '0–100, Geneva-style',
      kind: 'numbers',
      numbers,
      numbersUseCase:
        'Use case: prices, addresses, phone numbers, bus lines.',
      drill: 'Read your own address and phone number aloud in French.',
    },
    {
      id: 3,
      title: 'First transaction',
      subtitle: 'Boulangerie / kiosk',
      kind: 'transaction',
      useCases: [
        { phrase: 'Je voudrais…', use: '"I would like…" (softer than "je veux")' },
        { phrase: 'Un / une…, s\'il vous plaît', use: 'ordering' },
        { phrase: "C'est combien ?", use: 'asking price' },
        { phrase: 'Voilà', use: 'handing something over' },
        { phrase: 'Avez-vous… ?', use: '"do you have…?"' },
      ],
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, je voudrais un café, s\'il vous plaît.',
          en: 'Hello, I would like a coffee, please.',
        },
        {
          speaker: 'B',
          fr: 'Voilà, ça fait trois francs cinquante.',
          en: "Here you go, that's three francs fifty.",
        },
        { speaker: 'A', fr: 'Merci, au revoir !', en: 'Thank you, goodbye!' },
      ],
      drill: 'Practice ordering three different items using "Je voudrais…, s\'il vous plaît."',
    },
    {
      id: 4,
      title: 'Consolidation & role-play',
      subtitle: 'Checkpoint',
      kind: 'roleplay',
      drill:
        'Combine Sessions 1–3 into one unscripted role-play. This is your checkpoint — if you can do this cold, Week 1 is done.',
      roleplaySteps: [
        { title: 'Enter and greet', hint: 'Bonjour Madame / Monsieur.' },
        {
          title: 'Ask for an item',
          hint: 'Je voudrais…, s\'il vous plaît.',
        },
        { title: 'Ask the price', hint: "C'est combien ?" },
        { title: 'Pay and hand it over', hint: 'Voilà.' },
        { title: 'Thank and leave', hint: 'Merci, au revoir ! Bonne journée !' },
      ],
    },
  ],
  vocab: [
    { fr: 'bonjour', en: 'hello / good day' },
    { fr: 'bonsoir', en: 'good evening' },
    { fr: 'merci', en: 'thank you' },
    { fr: "s'il vous plaît", en: 'please' },
    { fr: 'voilà', en: 'here you go / there it is' },
    { fr: 'combien', en: 'how much' },
    { fr: 'franc', en: 'franc (currency)' },
    { fr: 'centime', en: 'centime (currency)' },
    { fr: 'je voudrais', en: 'I would like' },
    { fr: 'avez-vous', en: 'do you have' },
    { fr: 'oui', en: 'yes' },
    { fr: 'non', en: 'no' },
    { fr: 'pardon', en: 'sorry / pardon' },
    { fr: 'excusez-moi', en: 'excuse me' },
    { fr: 'dix', en: 'ten' },
    { fr: 'vingt', en: 'twenty' },
    { fr: 'trente', en: 'thirty' },
    { fr: 'septante', en: 'seventy (Swiss)' },
    { fr: 'nonante', en: 'ninety (Swiss)' },
    { fr: 'cent', en: 'one hundred' },
  ],
}

export const weeks: Week[] = [week1]
