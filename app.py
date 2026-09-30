import math
import os
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="The Food at Home", layout="wide")

if os.path.exists("logo.png"):
    col_l, col_center, col_r = st.columns([2,2,2])
    with col_center:
        st.image("logo.png", width=750)

lt, gt = "<", ">"
header_html = (
    f"{lt}h1 style='text-align: center; margin-bottom: 0.5rem; font-weight: 700;'{gt}The Food at Home{lt}/h1{gt}"
    f"{lt}p style='text-align: center; font-size: 1.1rem; max-width: 720px; margin: 0 auto 2rem auto; line-height: 1.5;'{gt}"
    f"Because there really is food at home. Turn what you already have in the kitchen into a meal, "
    f"ranked by fewest missing ingredients and grocery cost.{lt}/p{gt}"
)

st.markdown(header_html, unsafe_allow_html=True)

GROCERY_COST_ESTIMATES = {
    "onion": 0.75,
    "garlic": 0.50,
    "butter": 1.25,
    "milk": 1.00,
    "heavy cream": 2.20,
    "egg": 0.50,
    "flour": 0.40,
    "sugar": 0.40,
    "brown sugar": 0.50,
    "tomato": 0.85,
    "canned tomatoes": 1.10,
    "tomato paste": 0.90,
    "tomato sauce": 1.10,
    "soy sauce": 0.75,
    "parmesan": 2.50,
    "cheddar": 2.00,
    "cheese": 2.00,
    "mozzarella": 2.25,
    "rice": 0.60,
    "pasta": 1.10,
    "noodles": 1.00,
    "beef": 4.50,
    "ground beef": 4.50,
    "chicken": 3.50,
    "chicken breast": 3.50,
    "bread": 1.50,
    "potato": 0.60,
    "oil": 0.50,
    "olive oil": 0.75,
    "vegetable oil": 0.50,
    "salt": 0.10,
    "pepper": 0.15,
    "black pepper": 0.15,
    "beans": 1.00,
    "black beans": 1.00,
    "chickpeas": 1.00,
    "lentils": 1.00,
    "tuna": 1.25,
    "canned tuna": 1.25,
    "bell pepper": 1.00,
    "carrot": 0.50,
    "spinach": 1.50,
    "eggplant": 1.50,
}

FALLBACK_SUBSTITUTIONS = {
    "onion": "shallots, scallions, leeks, or onion powder",
    "garlic": "garlic powder, minced jarred garlic, or shallots",
    "butter": "olive oil, ghee, or neutral vegetable oil",
    "milk": "oat milk, almond milk, soy milk, or water with melted butter",
    "heavy cream": "whole milk whisked with melted butter, or coconut cream",
    "egg": "ground flaxseed with water (1 tbsp : 3 tbsp), or applesauce",
    "flour": "cornstarch (use half amount), arrowroot, or oat flour",
    "sugar": "honey, maple syrup, brown sugar, or agave",
    "tomato": "canned crushed tomatoes, tomato paste loosened with water, or passata",
    "tomato paste": "canned tomato sauce simmered down, or crushed tomatoes",
    "soy sauce": "tamari, coconut aminos, or Worcestershire sauce with a pinch of salt",
    "parmesan": "pecorino romano, grana padano, or nutritional yeast",
    "cheddar": "colby, gouda, or monterey jack",
    "mozzarella": "provolone, Monterey jack, or white cheddar",
    "rice": "quinoa, farro, couscous, or riced cauliflower",
    "pasta": "rice noodles, soba noodles, or zucchini ribbons",
    "beef": "ground turkey, firm brown lentils, portobello mushrooms, or pork",
    "chicken": "turkey cutlets, firm pressed tofu, or cooked chickpeas",
    "black beans": "pinto beans, kidney beans, or lentils",
    "bread": "tortillas, pita, English muffins, or cooked grains",
    "eggplant": "zucchini, yellow squash, or portobello mushroom caps",
}

EXCLUSIONS = {
    "egg": ["eggplant", "egg plant", "egg roll", "egg rolls"],
    "pea": ["peanut", "peanuts", "peanut butter"],
    "corn": ["cornbread", "cornstarch", "corn flour"],
}


def normalize_words(text):
    clean = text.lower().replace(",", " ").replace(".", " ").replace("-", " ")
    tokens = clean.split()
    normalized = []
    for t in tokens:
        if t.endswith("ies"):
            t = t[:-3] + "y"
        elif t.endswith("es") and not t.endswith("ches") and not t.endswith("shes"):
            t = t[:-2]
        elif t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        normalized.append(t)
    return normalized


def ingredient_matches(pantry_raw, recipe_raw):
    p_lower = pantry_raw.lower().strip()
    r_lower = recipe_raw.lower().strip()

    for staple, bad_list in EXCLUSIONS.items():
        if staple == p_lower or staple in p_lower.split():
            for bad_item in bad_list:
                if bad_item in r_lower:
                    return False

    p_tokens = normalize_words(p_lower)
    r_tokens = normalize_words(r_lower)

    for pt in p_tokens:
        if len(pt) in range(3, 40) and pt in r_tokens:
            return True

    return False


def estimate_missing_cost(missing_items):
    total_cost = 0.0
    for item in missing_items:
        clean = item.lower().strip()
        matched_price = None
        for staple, price in GROCERY_COST_ESTIMATES.items():
            if staple in clean or clean in staple:
                matched_price = price
                break
        total_cost += matched_price if matched_price is not None else 1.25
    return round(total_cost, 2)


def get_substitute_notes(missing_list):
    if not missing_list:
        return ["You have all necessary ingredients on hand."]

    notes = []
    for item in missing_list:
        item_lower = item.lower().strip()
        found = None
        for k, v in FALLBACK_SUBSTITUTIONS.items():
            if k in item_lower or item_lower in k:
                found = v
                break

        if found:
            notes.append(f"{item.title()}: Swap with {found}.")
        else:
            notes.append(f"{item.title()}: Omit if unavailable or pick up at the store.")
    return notes


def fetch_single_meal(mid):
    detail_url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={mid}"
    try:
        res = requests.get(detail_url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data and data.get("meals"):
                return data["meals"][0]
    except Exception:
        pass
    return None


def match_recipe_ingredients(recipe_ingredients, pantry_items):
    used = []
    missed = []
    for r_ing in recipe_ingredients:
        matched = False
        for p_ing in pantry_items:
            if ingredient_matches(p_ing, r_ing):
                matched = True
                break
        if matched:
            used.append(r_ing)
        else:
            missed.append(r_ing)
    return used, missed


def evaluate_themealdb(pantry_items, meal_filter="All Categories"):
    pantry_cleaned = [p.strip() for p in pantry_items if p.strip()]
    if not pantry_cleaned:
        return pd.DataFrame()

    candidate_meals = {}
    for ing in pantry_cleaned:
        tokens = normalize_words(ing)
        clean = tokens[0] if tokens else ing.lower()
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={clean}"
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data and data.get("meals"):
                    for m in data["meals"]:
                        mid = m["idMeal"]
                        if mid not in candidate_meals:
                            candidate_meals[mid] = m["strMeal"]
        except Exception:
            continue

    if not candidate_meals:
        return pd.DataFrame()

    meal_ids = list(candidate_meals.keys())
    with ThreadPoolExecutor(max_workers=10) as executor:
        api_meals = list(executor.map(fetch_single_meal, meal_ids))

    results = []
    seen_titles = set()

    for meal in api_meals:
        if not meal:
            continue

        title = meal.get("strMeal", "")
        if title.lower() in seen_titles:
            continue

        category = meal.get("strCategory", "Main")
        if meal_filter == "Savory Meals Only" and category.lower() == "dessert":
            continue
        elif meal_filter == "Breakfast" and category.lower() != "breakfast":
            continue
        elif meal_filter == "Desserts / Baking" and category.lower() != "dessert":
            continue

        recipe_ings = []
        for i in range(1, 21):
            val = meal.get(f"strIngredient{i}")
            if val and val.strip():
                recipe_ings.append(val.strip())

        used, missed = match_recipe_ingredients(recipe_ings, pantry_cleaned)
        if not used:
            continue

        total = len(used) + len(missed)
        pct = (len(used) / total) * 100 if total != 0 else 0
        cost = estimate_missing_cost(missed)

        link = (
            meal.get("strYoutube")
            or meal.get("strSource")
            or f"https://www.themealdb.com/meal/{meal['idMeal']}"
        )

        seen_titles.add(title.lower())
        results.append(
            {
                "title": title,
                "cuisine": meal.get("strArea", "International"),
                "category": category,
                "image": meal.get("strMealThumb", ""),
                "recipe_link": link,
                "instructions": meal.get("strInstructions", "Instructions available on site or video."),
                "used": used,
                "missed": missed,
                "missed_count": len(missed),
                "match_pct": round(pct, 1),
                "est_cost": cost,
            }
        )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    return df.sort_values(
        by=["missed_count", "est_cost", "match_pct"],
        ascending=[True, True, False]
    ).reset_index(drop=True)


if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "page_number" not in st.session_state:
    st.session_state.page_number = 1

col_input, col_cat = st.columns([3, 1.2])
with col_input:
    ingredients_input = st.text_input(
        "What ingredients are in your kitchen?",
        value="eggs, potatoes, onion",
        placeholder="e.g. eggs, potatoes, tomatoes, rice, chicken",
    )
with col_cat:
    selected_meal_type = st.selectbox(
        "Meal Type",
        ["All Categories", "Savory Meals Only", "Breakfast", "Desserts / Baking"],
        index=0,
    )

col_b_l, col_b_mid, col_b_r = st.columns([1.8, 1, 1.8])
with col_b_mid:
    find_btn = st.button("Find Recipes", type="primary", use_container_width=True)

if find_btn:
    pantry_list = [x.strip() for x in ingredients_input.split(",") if x.strip()]
    if not pantry_list:
        st.warning("Please specify at least one ingredient.")
    else:
        with st.spinner("Searching pantry recipes across culinary catalog..."):
            df = evaluate_themealdb(pantry_list, meal_filter=selected_meal_type)
            st.session_state.search_results = df
            st.session_state.page_number = 1

PAGE_SIZE = 50

if st.session_state.search_results is not None:
    results_df = st.session_state.search_results
    total_count = len(results_df)

    if results_df.empty:
        st.info("No matching recipes found for those ingredients. Try basic staples like rice, chicken, or eggs.")
    else:
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))

        st.session_state.page_number = max(1, min(st.session_state.page_number, total_pages))
        curr_page = st.session_state.page_number

        start_idx = (curr_page - 1) * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, total_count)
        page_slice = results_df.iloc[start_idx:end_idx]

        st.caption(
            f"Showing {start_idx + 1} to {end_idx} of {total_count} matching dishes (Page {curr_page} of {total_pages})."
        )
        st.write("")

        for _, meal in page_slice.iterrows():
            with st.container(border=True):
                col_thumb, col_details = st.columns([1, 2.5])

                with col_thumb:
                    if meal["image"]:
                        st.image(meal["image"], use_container_width=True)
                        st.caption("Photo serves as culinary reference and may vary slightly from listed prep.")

                with col_details:
                    st.subheader(meal["title"])
                    st.caption(f"{meal['cuisine']} cuisine - {meal['category']}")

                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        if meal["missed_count"] == 0:
                            st.write("Status: 100% Match (Pantry Ready)")
                        else:
                            st.write(f"Match: {meal['match_pct']}% ({meal['missed_count']} missing items)")
                    with col_m2:
                        if meal["missed_count"] == 0:
                            st.write("Estimated Grocery Cost: $0.00")
                        else:
                            st.write(f"Estimated Grocery Cost: ~${meal['est_cost']:.2f}")

                    used_str = ", ".join(meal["used"]) if meal["used"] else "None"
                    st.write(f"In your pantry: {used_str}")

                    missed_str = ", ".join(meal["missed"]) if meal["missed"] else "None"
                    st.write(f"Missing items: {missed_str}")

                    with st.expander("Substitution Guidance and Cooking Instructions"):
                        subs = get_substitute_notes(meal["missed"])
                        st.write("Substitutions:")
                        for s in subs:
                            st.write(f"- {s}")

                        st.write("---")
                        st.write("Cooking Steps:")
                        st.write(meal["instructions"])

                        st.link_button("Watch Video Walkthrough", meal["recipe_link"])

        st.write("---")
        _, col_nav_left, col_nav_input, col_nav_right, _ = st.columns([2, 0.8, 1.4, 0.8, 2])

        with col_nav_left:
            if st.button("Previous", disabled=(curr_page == 1), use_container_width=True):
                st.session_state.page_number -= 1
                st.rerun()

        with col_nav_input:
            selected_page = st.number_input(
                f"Page (of {total_pages})",
                min_value=1,
                max_value=total_pages,
                value=curr_page,
                step=1,
                label_visibility="collapsed",
            )
            if selected_page != curr_page:
                st.session_state.page_number = int(selected_page)
                st.rerun()

        with col_nav_right:
            if st.button("Next", disabled=(curr_page == total_pages), use_container_width=True):
                st.session_state.page_number += 1
                st.rerun()
