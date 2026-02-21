# 🆓 FREE AI Recommendation System Setup Guide

## ✅ 100% FREE Solutions - No Credit Card Required!

This guide shows you how to use the AI recommendation system **completely FREE** with multiple options.

---

## 🎯 Free Options (Ranked Best to Worst)

### 1. **Groq API** ⭐ BEST FREE OPTION
- **Free Tier**: 14,400 requests/day (600 requests/hour)
- **Speed**: Very fast (sub-second responses)
- **Quality**: Excellent (uses Llama 3.1 model)
- **Setup**: 2 minutes
- **Cost**: $0 forever

### 2. **Hugging Face Inference API**
- **Free Tier**: 1,000 requests/month
- **Speed**: Medium (2-5 seconds)
- **Quality**: Good
- **Setup**: 3 minutes
- **Cost**: $0

### 3. **Rule-Based (No API)**
- **Free Tier**: Unlimited
- **Speed**: Instant
- **Quality**: Good for basic extraction
- **Setup**: 0 minutes (works out of the box)
- **Cost**: $0 forever

---

## 🚀 Quick Setup - Groq (Recommended)

### Step 1: Get Free Groq API Key

1. Go to: https://console.groq.com/
2. Click **"Sign Up"** (use Google/GitHub/Email)
3. No credit card required!
4. Go to **"API Keys"** section
5. Click **"Create API Key"**
6. Copy your key (starts with `gsk_...`)

### Step 2: Add to `.env` File

```env
# Groq API (FREE - 14,400 requests/day)
GROQ_API_KEY=gsk_your_key_here

# Optional: Hugging Face (if you want backup)
HUGGINGFACE_API_TOKEN=your_hf_token_here

# Optional: OpenAI (only if you want paid option)
# OPENAI_API_KEY=sk-... (not needed for free)
```

### Step 3: Install Groq Package

```bash
pip install groq
```

### Step 4: Done! 🎉

The system will automatically use Groq (free) instead of OpenAI (paid).

---

## 🔧 Alternative: Hugging Face (Free)

### Step 1: Get Hugging Face Token

1. Go to: https://huggingface.co/
2. Sign up (free)
3. Go to: https://huggingface.co/settings/tokens
4. Click **"New token"**
5. Copy token (starts with `hf_...`)

### Step 2: Add to `.env`

```env
HUGGINGFACE_API_TOKEN=hf_your_token_here
```

### Step 3: Install Package

```bash
pip install requests
```

---

## 🎁 Option 3: Rule-Based (No API, Always Works)

**This works immediately with NO setup!**

The system automatically falls back to rule-based extraction if no API keys are set. It:
- ✅ Extracts skills from resume text
- ✅ Estimates experience years
- ✅ Generates professional summary
- ✅ Recommends job roles
- ✅ Finds missing skills
- ✅ Matches jobs with skills

**No API key needed!** Just use the system and it works.

---

## 📋 Updated Code Files

I've created free versions:

1. **`Demoapp_free.py`** - Free LLM wrapper with all free options
2. **`resume_extraction_service_free.py`** - Free resume parser (no OpenAI)
3. **`Demoapp.py`** - Updated to use free options first

The system now:
- ✅ Tries Groq first (if key set)
- ✅ Falls back to rule-based (always works)
- ✅ Only uses OpenAI if explicitly set (optional)

---

## 🧪 Test It

### Test Rule-Based (No Setup):

```python
from Demoapp_free import run_model_free_rule_based

resume_text = """
John Doe
Software Engineer with 3 years experience.
Skills: Python, React, Node.js, SQL
"""

result = run_model_free_rule_based(resume_text)
print(result)
```

### Test Groq (After Setup):

```python
from Demoapp import run_model

resume_text = "Your resume text here..."
result = run_model(resume_text)
print(result["method"])  # Should show "groq_free"
```

---

## 💰 Cost Comparison

| Option | Cost | Requests/Day | Speed | Quality |
|--------|------|--------------|-------|---------|
| **Groq** | $0 | 14,400 | ⚡ Fast | ⭐⭐⭐⭐⭐ |
| **Hugging Face** | $0 | ~33/day | 🐢 Medium | ⭐⭐⭐⭐ |
| **Rule-Based** | $0 | Unlimited | ⚡ Instant | ⭐⭐⭐ |
| **OpenAI** | $0.15/1M tokens | Unlimited* | ⚡ Fast | ⭐⭐⭐⭐⭐ |

*OpenAI requires payment after free credits

---

## 🎯 Recommended Setup

**For Best Free Experience:**

1. ✅ Get Groq API key (free, 14,400 requests/day)
2. ✅ Add to `.env`: `GROQ_API_KEY=...`
3. ✅ Install: `pip install groq`
4. ✅ Done! System uses Groq automatically

**For Zero Setup:**

- Just use the system! Rule-based extraction works immediately.
- No API keys needed.
- Good for basic skill extraction and matching.

---

## 🔄 How It Works

The system tries options in this order:

1. **Groq** (if `GROQ_API_KEY` set) → Best free option
2. **Hugging Face** (if `HUGGINGFACE_API_TOKEN` set) → Backup
3. **Rule-Based** (always works) → Fallback
4. **OpenAI** (if `OPENAI_API_KEY` set) → Optional paid

You'll see which method was used in the response:
```json
{
  "method": "groq_free",  // or "rule_based_free" or "openai_paid"
  ...
}
```

---

## ✅ Everything is FREE!

- ✅ Resume extraction - FREE (rule-based)
- ✅ Skill extraction - FREE (pattern matching)
- ✅ Job matching - FREE (cosine similarity)
- ✅ LLM analysis - FREE (Groq or rule-based)
- ✅ No credit card needed
- ✅ No payment required
- ✅ Works immediately

---

## 🐛 Troubleshooting

### "No API key found"
- ✅ **This is OK!** System uses rule-based extraction (free, no API needed)
- ✅ Or set `GROQ_API_KEY` for better results

### "Groq import error"
```bash
pip install groq
```

### "Hugging Face not working"
- Rule-based fallback will work automatically
- Or check your token is valid

---

## 🎉 You're All Set!

The system is now **100% FREE** and works immediately:

1. ✅ No OpenAI key needed
2. ✅ No payment required
3. ✅ Works out of the box
4. ✅ Optional: Add Groq key for better results

**Just start using it!** 🚀

