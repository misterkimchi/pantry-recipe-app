import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Pantry Chef: Recipe Matcher", layout="wide")

st.title("Pantry Chef")
st.caption(
    "Turn available kitchen ingredients into meals. Ranked by pantry overlap with practical culinary substitutions."
)

with st.sidebar:
    st.subheader("Preferences")
    max_recipes = st.slider(
        "Candidate recipes to evaluate", min_value=3, max_value=8, value=5
    )
    st.markdown("---")
    st.caption(
        "Open Access: Powered by TheMealDB culinary catalog. No API tokens or daily search limits required."
    )

FALLBACK_SUBSTITUTIONS = {
    "onion": "shallots, scallions, or leeks",
    "garlic": "garlic powder, minced shallots, or chives",
    "butter": "olive oil, ghee, or neutral vegetable oil",
    "milk": "oat milk, almond milk, or equal parts yogurt and water",
    "heavy cream": "whole milk whisked with melted butter, or coconut milk",
    "egg": "ground flaxseed with water (1 tbsp : 3 tbsp), or applesauce",
    "flour": "cornstarch (use half amount), arrowroot, or oat flour",
    "sugar": "honey, maple syrup, or agave nectar",
    "tomato": "canned crushed tomatoes, tomato paste loosened with water, or passata",
    "soy sauce": "tamari, coconut aminos, or Worcestershire sauce",
    "parmesan": "pecorino romano, grana padano, or nutritional yeast",
    "rice": "quinoa, farro, or couscous",
    "beef": "ground turkey, firm lentils, mushrooms, or pork",
    "chicken": "turkey tenderloin, firm tofu, or canned chickpeas",
    "cheese": "mozzarella, provolone, or white cheddar",
}


def get_substitute_notes(missing_list):
    if not missing_list:
        return ["You have all necessary ingredients on hand."]

    notes = []
    for item in missing_list:
        item_lower = item.lower().strip()
        found = None
        for k, v in FALLBACK_SUBSTITUTIONS.items():
            if k in item_lower:
                found = v
                break

        if found:
            notes.append(f"**{item.title()}**: Swap with {found}.")
        else:
            notes.append(
                f"**{item.title()}**: Optional or pick up on next grocery run."
            )
    return notes


def search_meals(pantry_items, limit=5):
    candidates = {}

    for item in pantry_items:
        clean = item.strip().replace(" ", "_")
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={clean}"
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data and data.get("meals"):
                    for m in data["meals"]:
                        mid = m["idMeal"]
                        if mid not in candidates:
                            candidates[mid] = {
                                "id": mid,
                                "title": m["strMeal"],
                                "thumb": m["strMealThumb"],
                            }
        except Exception:
            continue

    if not candidates:
        return pd.DataFrame()

    results = []
    pantry_set = {p.lower().strip() for p in pantry_items}

    for mid in list(candidates.keys())[:limit]:
        detail_url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={mid}"
        try:
            res = requests.get(detail_url, timeout=5)
            if res.status_code != 200:
                continue
            meal = res.json()["meals"][0]
        except Exception:
            continue

        ingredients = []
        for i in range(1, 21):
            val = meal.get(f"strIngredient{i}")
            if val and val.strip():
                ingredients.append(val.strip())

        used = []
        missed = []
        for ing in ingredients:
            ing_lower = ing.lower()
            if any(p in ing_lower or ing_lower in p for p in pantry_set):
                used.append(ing)
            else:
                missed.append(ing)

        total = len(used) + len(missed)
        pct = (len(used) / total) * 100 if total > 0 else 0

        link = (
            meal.get("strYoutube")
            or meal.get("strSource")
            or f"https://www.themealdb.com/meal/{mid}"
        )

        results.append(
            {
                "id": mid,
                "title": meal["strMeal"],
                "cuisine": meal.get("strArea", "General"),
                "category": meal.get("strCategory", "Main"),
                "image": meal["strMealThumb"],
                "recipe_link": link,
                "used": used,
                "missed": missed,
                "missed_count": len(missed),
                "match_pct": round(pct, 1),
            }
        )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    return df.sort_values(
        by=["missed_count", "match_pct"], ascending=[True, False]
    ).reset_index(drop=True)


ingredients_input = st.text_input(
    "What ingredients are in your kitchen?",
    value="chicken, rice, onion, garlic",
    placeholder="e.g. eggs, potatoes, tomatoes, pasta",
)

if st.button("Find Recipes", type="primary"):
    pantry_list = [
        x.strip() for x in ingredients_input.split(",") if x.strip()
    ]

    if not pantry_list:
        st.warning("Please specify at least one ingredient.")
    else:
        with st.spinner("Analyzing ingredients and checking recipe catalogs..."):
            meals_df = search_meals(pantry_list, limit=max_recipes)

            if meals_df.empty:
                st.info(
                    "No matches found for that combination. Try common staples like chicken, beef, potato, or onion."
                )
            else:
                st.write("")
                for _, meal in meals_df.iterrows():
                    with st.container(border=True):
                        col_thumb, col_details = st.columns([1, 2.5])

                        with col_thumb:
                            st.image(meal["image"], use_container_width=True)

                        with col_details:
                            st.subheader(meal["title"])
                            st.caption(
                                f"{meal['cuisine']} cuisine · {meal['category']}"
                            )

                            if meal["missed_count"] == 0:
                                st.write("**Match:** 100% (Ready to cook)")
                            else:
                                st.write(
                                    f"**Match:** {meal['match_pct']}% (Missing {meal['missed_count']} items)"
                                )

                            used_str = (
                                ", ".join(meal["used"])
                                if meal["used"]
                                else "None"
                            )
                            st.write(f"**In your pantry:** {used_str}")

                            missed_str = (
                                ", ".join(meal["missed"])
                                if meal["missed"]
                                else "None"
                            )
                            st.write(f"**Missing items:** {missed_str}")

                            with st.expander(
                                "Substitution Guidance and Cooking Steps"
                            ):
                                subs = get_substitute_notes(meal["missed"])
                                for s in subs:
                                    st.write(s)
                                st.link_button(
                                    "Open Instructions and Video",
                                    meal["recipe_link"],
                                )
