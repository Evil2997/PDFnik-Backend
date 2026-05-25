PDFnik сейчас отличается от большинства существующих решений не качеством самой транскрибации, а уровнем архитектуры и контроля над пайплайном.

## Transcript APIs (AssemblyAI, Deepgram)

Эти сервисы:

* дают transcript;
* summaries;
* timestamps;
* chapters;
* speech intelligence.

Но они заканчиваются на:

```text
audio/video → JSON
```

PDFnik идёт дальше:

```text
media → normalized schema → structured blocks → deterministic document
```

То есть transcript для PDFnik — только сырьё.

---

## Multimodal video AI (Twelve Labs)

Twelve Labs ближе всех к будущему направлению PDFnik.

Они сильны в:

* semantic video understanding;
* frame analysis;
* embeddings;
* scene search;
* multimodal retrieval.

Но они не document engine.

Они:

```text
video understanding infrastructure
```

А PDFnik:

```text
document orchestration system
```

---

## OpenAI / Gemini / Claude

Foundation-модели умеют:

* reasoning;
* summaries;
* article generation;
* image understanding.

Но сами по себе они:

* не управляют пайплайном;
* не гарантируют структуру;
* не дают deterministic rendering;
* не являются document systems.

PDFnik использует LLM как слой анализа, а не как конечный продукт.

---

## SaaS-конвейеры (BibiGPT, Fireflies, Otter)

Они уже ближе к “готовому продукту”:

* transcript;
* summaries;
* статьи;
* export.

Но почти всегда это:

* black-box;
* фиксированный UX;
* мало контроля;
* нет extensible architecture;
* нет canonical schema.

PDFnik же строится как:

* extensible engine;
* provider-agnostic system;
* programmable pipeline.

---

# Главное отличие PDFnik

PDFnik архитектурно строится вокруг идеи:

```text
Document = process, not response
```



То есть:

* transcript,
* OCR,
* summaries,
* frame analysis,
* external APIs,
* LLM,
* user input

— это только стадии сборки итогового документа.

---

# Куда реально движется PDFnik

Не в сторону:

* “бота с PDF”;
* “транскрибатора”;
* “summary generator”.

А в сторону:

```text
AI-native document infrastructure
```

или:

```text
Multimodal Document Engine
```

---

# Самое сильное потенциальное преимущество PDFnik

Не собственная модель.

А:

* orchestration;
* canonical schema;
* provider abstraction;
* deterministic rendering;
* structured artifacts;
* explainable pipeline;
* multimodal assembly.

Именно это сейчас почти никто не объединяет в одном продукте.
