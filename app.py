import pandas as pd
import requests
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Smart Pantry Matcher", page_icon="🍳", layout="wide"
)

st.title("🍳 Smart Pantry-to-Recipe Matcher")
st.markdown(
    "Enter the ingredients you have on hand. Recipes are ranked by **highest pantry match** first, complete with chef substitution tips."
)

# Sidebar for settings & API key
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input(
        "Spoonacular API Key",
        type="password",
        help="Get your key at spoonacular.com/food-api",
    )
    result_count = st.slider(
        "Number of recipes to fetch", min_value=3, max_value=10, value=5
    )

# Fallback substitution knowledge base
FALLBACK_SUBSTITUTIONS = {
    "onion powder": "minced fresh onions, shallots, or garlic powder",
    "garlic cloves": "garlic powder, minced jarred garlic, or shallots",
    "bell pepper": "poblano pepper, celery, or zucchini for crunch",
    "spaghetti sauce": "canned crushed tomatoes, tomato paste with water, or salsa",
    "mozzarella cheese": "cheddar, provolone, or parmesan",
    "cornstarch": "all-purpose flour (use 2x amount) or arrowroot",
    "ginger": "ground ginger powder or allspice",
    "soy sauce": "tamari, coconut aminos, or Worcestershire sauce with a pinch of salt",
    "pineapple chunks": "canned peaches, mango chunks, or an extra splash of sweet sauce",
    "tomato sauce": "tomato paste mixed with equal parts water",
}


def get_online_substitute(key, ingredient_name):
    """Queries Spoonacular's substitution endpoint."""
    url = "https://api.spoonacular.com/food/ingredients/substitutes"
    params = {"apiKey": key, "ingredientName": ingredient_name}
    try:
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success" and data.get("substitutes"):
                return data["substitutes"][0]
    except Exception:
        pass
    return None


def get_recipe_details(key, recipe_id):
    """Pulls full source URL and prep time for a recipe."""
    url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
    try:
        res = requests.get(url, params={"apiKey": key}, timeout=4)
        if res.status_code == 200:
            info = res.json()
            return info.get("sourceUrl", "#"), info.get(
                "readyInMinutes", "Unknown"
            )
    except Exception:
        pass
    return f"https://spoonacular.com/recipes/{recipe_id}", "Unknown"


def analyze_substitutions(key, missing_items):
    """Hybrid online-first, offline-fallback substitution advice."""
    if not missing_items:
        return ["You have 100% of the ingredients required!"]

    notes = []
    for item in missing_items:
        item_clean = item.lower().strip()

        # 1. Online check
        online = get_online_substitute(key, item_clean)
        if online:
            notes.append(f"**{item.title()}**: {online} *(Online verified)*")
            continue

        # 2. Offline fallback
        matched_rule = None
        for rule_key, sub_val in FALLBACK_SUBSTITUTIONS.items():
            if rule_key in item_clean:
                matched_rule = sub_val
                break

        if matched_rule:
            notes.append(
                f"**{item.title()}**: Swap with {matched_rule} *(Culinary fallback)*"
            )
        else:
            notes.append(
                f"**{item.title()}**: Optional staple or purchase at store."
            )

    return notes


# Main search input
user_ingredients = st.text_input(
    "What ingredients do you have?",
    value="chicken, garlic, rice, soy sauce",
    placeholder="e.g. beef, potatoes, onions, carrots",
)

if st.button("Find Recipes", type="primary"):
    if not api_key:
        st.error(
            "Please provide your Spoonacular API Key in the left sidebar."
        )
    elif not user_ingredients.strip():
        st.warning("Please enter at least one ingredient.")
    else:
        with st.spinner("Searching pantry recipes and ranking matches..."):
            endpoint = "https://api.spoonacular.com/recipes/findByIngredients"
            params = {
                "apiKey": api_key,
                "ingredients": user_ingredients,
                "number": result_count,
                "ranking": 2,
                "ignorePantry": True,
            }

            try:
                resp = requests.get(endpoint, params=params, timeout=10)
                if resp.status_code != 200:
                    st.error(
                        f"API Error ({resp.status_code}). Verify your key and daily quota."
                    )
                    st.stop()
                raw_recipes = resp.json()
            except Exception as e:
                st.error(f"Network error: {e}")
                st.stop()

            if not raw_recipes:
                st.info("No recipes found matching those pantry items.")
                st.stop()

            # Process into DataFrame
            records = []
            for r in raw_recipes:
                used = [i["name"] for i in r.get("usedIngredients", [])]
                missed = [i["name"] for i in r.get("missedIngredients", [])]
                total = len(used) + len(missed)
                match_pct = (len(used) / total) * 100 if total > 0 else 0

                records.append(
                    {
                        "id": r["id"],
                        "title": r["title"],
                        "image": r["image"],
                        "used_items": used,
                        "missed_items": missed,
                        "missed_count": len(missed),
                        "match_pct": round(match_pct, 1),
                    }
                )

            df = (
                pd.DataFrame(records)
                .sort_values(
                    by=["missed_count", "match_pct"], ascending=[True, False]
                )
                .reset_index(drop=True)
            )

            st.success(
                f"Found {len(df)} matching recipes! Sorted in descending match order."
            )
            st.write("---")

            # Render each recipe card
            for _, row in df.iterrows():
                recipe_link, cook_time = get_recipe_details(api_key, row["id"])
                sub_advice = analyze_substitutions(api_key, row["missed_items"])

                col_img, col_info = st.columns([1, 2.5])

                with col_img:
                    st.image(row["image"], use_container_width=True)

                with col_info:
                    st.subheader(row["title"])

                    # Match badge
                    if row["missed_count"] == 0:
                        st.markdown("🟢 **100% Match (0 missing ingredients!)**")
                    else:
                        st.markdown(
                            f"🟠 **{row['match_pct']}% Match** (Needs {row['missed_count']} extra item{'s' if row['missed_count'] > 1 else ''})"
                        )

                    st.write(f"⏱ **Cook Time:** ~{cook_time} mins")
                    st.write(f"**You Have:** {', '.join(row['used_items'])}")

                    if row["missed_items"]:
                        st.write(
                            f"**Missing Items:** {', '.join(row['missed_items'])}"
                        )

                    with st.expander("💡 Substitution Advice"):
                        for tip in sub_advice:
                            st.write(tip)

                    st.link_button("View Cooking Steps →", recipe_link)

                st.write("---")
