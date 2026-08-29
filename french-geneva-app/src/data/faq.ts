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
    id: 'du-de-la-des',
    question: 'What are "du", "de la", and "des" for?',
    answer:
      'These are "partitive articles" — used for an unspecified amount of something, like English "some". "Du" goes with masculine nouns (du pain, some bread), "de la" with feminine nouns (de la confiture, some jam), and "des" with plurals (des tomates, some tomatoes). At the market you\'ll hear these constantly ("Je voudrais du fromage") — you don\'t need to master the grammar yet, just recognize the pattern.',
    keywords: [
      'du', 'de la', 'des', 'partitive', 'some', 'du de la des',
    ],
  },
  {
    id: 'cher-chere',
    question: 'Why is it "cher" sometimes and "chère" other times?',
    answer:
      'French adjectives change spelling to match the gender of the noun they describe — "cher" for masculine ("un billet cher"), "chère" for feminine ("une chambre chère"). Most adjectives just add an "-e" for the feminine form. It rarely changes the pronunciation much, so don\'t stress over it in speech — it matters more in writing.',
    keywords: ['cher', 'chère', 'adjective agreement', 'masculine feminine adjective'],
  },
  {
    id: 'quest-ce-que',
    question: 'What does "qu\'est-ce que" mean?',
    answer:
      'It\'s a set phrase meaning roughly "what is it that…", used to start a question about a thing — "Qu\'est-ce que vous recommandez ?" ("What do you recommend?"). It sounds like one long word when spoken quickly ("kess-ke"). Just memorize it as a fixed opener rather than analyzing the grammar.',
    keywords: ['qu\'est-ce que', 'quest ce que', 'kesse', 'what question'],
  },
  {
    id: 'comment-allez-vous-ca-va',
    question: '"Comment allez-vous ?" vs "Ça va ?" — what\'s the difference?',
    answer:
      '"Comment allez-vous ?" is the full, formal way to ask "How are you?" and pairs with "vous". "Ça va ?" is a casual shortcut used with people you know or in relaxed settings, and the reply is often just "Ça va" (I\'m fine / it\'s going okay). For strangers and transactions, stick with "Comment allez-vous ?".',
    keywords: ['comment allez-vous', 'ça va', 'how are you'],
  },
  {
    id: 'profession-no-article',
    question: 'Why is it "Je suis professeur" and not "Je suis un professeur"?',
    answer:
      'French drops the article ("un/une") before a profession, nationality, or religion used with "être" — "Je suis professeur", "Je suis suisse". The article comes back as soon as you add a description: "Je suis un bon professeur" ("I am a good teacher"). This trips up a lot of English speakers since English always keeps the "a".',
    keywords: ['je suis professeur', 'profession', 'article', 'un professeur', 'job', 'occupation'],
  },
  {
    id: 'on-meaning',
    question: 'What does "on" mean?',
    answer:
      '"On" is an all-purpose informal subject pronoun that usually means "we" in everyday spoken French — "On se voit quand ?" = "When shall we meet?". It technically means "one/people in general" (like formal English "one does..."), but in casual conversation it has mostly replaced "nous". Conjugate the verb as "il/elle" (on va, on fait, on voit).',
    keywords: ['on', 'on se voit', 'nous', 'we', 'on meaning'],
  },
  {
    id: 'depuis-usage',
    question: 'How does "depuis" work for talking about time?',
    answer:
      '"Depuis" means "since" or "for", used with a present-tense verb to describe something that started in the past and is still true now — "J\'habite ici depuis six mois" ("I\'ve been living here for six months", and I still do). English switches to "have been -ing"; French just stays in the present tense with "depuis".',
    keywords: ['depuis', 'since', 'for', 'duration', 'depuis combien de temps'],
  },
  {
    id: 'au-a-la',
    question: 'What\'s the difference between "au" and "à la"?',
    answer:
      '"Au" is just "à + le" glued together for masculine nouns — you\'ll never say "à le". "À la" is used as-is for feminine nouns, and "à + les" becomes "aux" for plurals. It shows up constantly in "avoir mal à" (j\'ai mal au dos vs. j\'ai mal à la tête) — same gender rule as un/une, just fused with "à".',
    keywords: ['au', 'à la', 'aux', 'a le', 'contraction', 'avoir mal'],
  },
  {
    id: 'avoir-mal-a',
    question: 'How does "avoir mal à" work?',
    answer:
      '"Avoir mal à" literally means "to have pain at" — you say "j\'ai mal à" plus the body part with its article: "j\'ai mal au ventre" (stomach), "j\'ai mal à la tête" (head), "j\'ai mal aux dents" (teeth, plural). It\'s the standard way to describe any ache in French — much more common than a separate verb for each type of pain.',
    keywords: ['avoir mal', 'j\'ai mal', 'pain', 'ache', 'hurt', 'symptoms'],
  },
  {
    id: 'combien-de-noun',
    question: 'How is "combien de" different from just "combien" ?',
    answer:
      '"Combien" alone asks "how much" in general, usually about price ("C\'est combien ?"). "Combien de" + a noun asks "how many/much of that specific thing" — "combien de pièces ?" (how many rooms), "combien de temps ?" (how much time). Same word, just paired up when you\'re asking about a specific noun rather than a price in isolation.',
    keywords: ['combien de', 'combien', 'how many', 'how much', 'pieces'],
  },
  {
    id: 'il-y-a',
    question: 'What does "il y a" mean?',
    answer:
      '"Il y a" means "there is" or "there are" — the same fixed phrase works for both singular and plural, so you never conjugate it differently. "Il y a un problème" (there\'s a problem), "il y a des charges" (there are fees). It also means "ago" with time expressions ("il y a six mois" = six months ago), but the "there is/are" sense is the one you\'ll use constantly.',
    keywords: ['il y a', 'there is', 'there are', 'ily a'],
  },
  {
    id: 'il-faut',
    question: 'What does "il faut" mean?',
    answer:
      '"Il faut" means "one must / it\'s necessary to" — like "il y a", it\'s a fixed impersonal phrase that never changes to match a person. "Il faut remplir un formulaire" (you need to fill out a form), "il faut deux documents" (two documents are needed). Follow it with either an infinitive verb or a noun.',
    keywords: ['il faut', 'must', 'necessary', 'need to', 'have to'],
  },
  {
    id: 'imperative-vous',
    question: 'Why do instructions say "remplissez" or "signez" instead of "vous remplissez"?',
    answer:
      'That\'s the imperative (command) form — used for instructions, requests, and official forms. For "vous", you just drop "vous" and keep the verb ending: "vous remplissez" → "remplissez !" (fill out!), "vous signez" → "signez !" (sign!). It\'s how forms, signs, and polite requests give commands in French.',
    keywords: ['remplissez', 'signez', 'cochez', 'imperative', 'command form'],
  },
  {
    id: 'passe-compose-intro',
    question: 'What\'s going on grammatically with "j\'ai vu" and "c\'était"?',
    answer:
      'Both describe something already finished — French\'s two main past tenses. "J\'ai vu" ("I saw") is the passé composé, built as avoir/être + a past participle (j\'ai vu, j\'ai fait, j\'ai appelé) — it\'s for a specific completed action. "C\'était" ("it was") is the imparfait, used for background description or an ongoing state in the past. At this stage, just recognize both as "this already happened" — you don\'t need the full conjugation system yet to describe most things.',
    keywords: ['j\'ai vu', 'c\'était', 'passé composé', 'imparfait', 'past tense', 'avoir vu'],
  },
  {
    id: 'negative-imperative',
    question: 'How do I say "don\'t do that" in French, like "ne touchez pas"?',
    answer:
      'Wrap the imperative in "ne… pas", same as any negative sentence: "touchez" (touch) → "ne touchez pas" (don\'t touch). With "tu" it works the same way: "ne touche pas". It\'s the same imperative form from Week 7\'s "signez"/"remplissez" — negating it costs you nothing extra to learn.',
    keywords: ['ne touchez pas', 'negative imperative', 'don\'t', 'ne pas'],
  },
  {
    id: 'travailler-dans-pour-chez',
    question: 'What\'s the difference between "travailler dans", "pour", and "chez"?',
    answer:
      'They point at different pieces of your job: "dans" names the field or industry ("je travaille dans la finance"), "pour" names who you work for as an organization ("je travaille pour une banque"), and "chez" names a specific employer more casually, like saying "at" ("je travaille chez UBS"). Pick based on which piece of information you\'re actually giving.',
    keywords: ['travailler dans', 'travailler pour', 'travailler chez', 'work in', 'work for'],
  },
  {
    id: 'avant-apres',
    question: 'What\'s the difference between "avant" and "après"?',
    answer:
      '"Avant" means "before" and "après" means "after" — opposites, easy to mix up under pressure. "Avant vendredi" (by/before Friday) sets a deadline; "après la réunion" (after the meeting) points to something that follows. Worth drilling as a pair, same as Week 2\'s "tout droit" vs "à droite".',
    keywords: ['avant', 'après', 'before', 'after', 'deadline'],
  },
]
