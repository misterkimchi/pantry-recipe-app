from concurrent.futures import ThreadPoolExecutor
import math
import os
import re
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="The Food at Home", layout="wide")

# Centered compact logo and title header
if os.path.exists("logo.png"):
    col_l, col_center, col_r = st.columns([2.5, 1, 2.5])
    with col_center:
        st.image("logo.png", width=110)

col_title_l, col_title_m, col_title_r = st.columns([1, 4, 1])
with col_title_m:
    st.title("The Food at Home")
    st.caption(
        "Because there really is food at home. Turn what you already have in the kitchen into a meal, ranked by fewest missing ingredients and grocery cost."
    )

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

LOCAL_PANTRY_CORPUS = [
    {
        "title": "Classic Egg Fried Rice",
        "category": "Savory Meals Only",
        "cuisine": "Asian",
        "ingredients": ["rice", "eggs", "soy sauce", "vegetable oil", "onion", "garlic"],
        "instructions": "Heat oil in a skillet over high heat. Sauté diced onions and minced garlic. Push to the side, scramble eggs, fold in chilled cooked rice, and season with soy sauce.",
        "image": "https://www.themealdb.com/images/media/meals/1529446352.jpg",
        "source": "https://en.wikipedia.org/wiki/Fried_rice",
    },
    {
        "title": "Spaghetti Aglio e Olio",
        "category": "Savory Meals Only",
        "cuisine": "Italian",
        "ingredients": ["pasta", "garlic", "olive oil", "black pepper", "parmesan"],
        "instructions": "Boil pasta in salted water. Gently sizzle sliced garlic in generous olive oil until golden. Toss pasta with the infused oil, a ladle of pasta cooking water, pepper, and cheese.",
        "image": "https://www.themealdb.com/images/media/meals/ustsqw1468250014.jpg",
        "source": "https://en.wikipedia.org/wiki/Spaghetti_aglio_e_olio",
    },
    {
        "title": "Country Potato and Onion Hash",
        "category": "Breakfast",
        "cuisine": "American",
        "ingredients": ["potatoes", "onion", "butter", "black pepper", "salt"],
        "instructions": "Dice potatoes small. Melt butter in a wide skillet, add potatoes and chopped onions, cover for 5 minutes, then crisp uncovered until golden brown on all sides.",
        "image": "https://www.themealdb.com/images/media/meals/1550441882.jpg",
        "source": "https://en.wikipedia.org/wiki/Hash_(food)",
    },
    {
        "title": "Skillet Tomato and Egg Shakshuka",
        "category": "Breakfast",
        "cuisine": "Middle Eastern",
        "ingredients": ["eggs", "canned tomatoes", "onion", "garlic", "olive oil", "salt"],
        "instructions": "Sauté chopped onions and garlic in olive oil. Pour in crushed tomatoes, season with salt and pepper, and simmer. Create small wells, crack eggs directly in, and cover until whites set.",
        "image": "https://www.themealdb.com/images/media/meals/g373701551450225.jpg",
        "source": "https://en.wikipedia.org/wiki/Shakshouka",
    },
    {
        "title": "Staple Lentil and Tomato Stew",
        "category": "Savory Meals Only",
        "cuisine": "Mediterranean",
        "ingredients": ["lentils", "canned tomatoes", "onion", "garlic", "olive oil", "carrots"],
        "instructions": "Sauté onions, garlic, and diced carrots in olive oil. Add dry lentils, canned tomatoes, and water or broth. Simmer covered for 30 minutes until lentils are tender.",
        "image": "https://www.themealdb.com/images/media/meals/58oia91564916529.jpg",
        "source": "https://en.wikipedia.org/wiki/Lentil_soup",
    },
    {
        "title": "Crispy Stovetop Frittata",
        "category": "Breakfast",
        "cuisine": "European",
        "ingredients": ["eggs", "potatoes", "cheese", "butter", "black pepper", "salt"],
        "instructions": "Thinly slice potatoes and soften in butter. Beat eggs with salt, pepper, and shredded cheese. Pour eggs over potatoes and cook on low heat until firm and golden.",
        "image": "https://www.themealdb.com/images/media/meals/quuxsx1511476154.jpg",
        "source": "https://en.wikipedia.org/wiki/Frittata",
    },
    {
        "title": "Simple Black Bean and Rice Bowl",
        "category": "Savory Meals Only",
        "cuisine": "Latin American",
        "ingredients": ["rice", "black beans", "onion", "garlic", "olive oil", "salt"],
        "instructions": "Warm drained black beans with sautéed garlic and onion. Serve hot over cooked white rice, finishing with olive oil and salt.",
        "image": "https://www.themealdb.com/images/media/meals/1529444830.jpg",
        "source": "https://en.wikipedia.org/wiki/Gallo_pinto",
    },
    {
        "title": "Toasted Tuna and Cheddar Melt",
        "category": "Savory Meals Only",
        "cuisine": "American",
        "ingredients": ["tuna", "bread", "cheddar", "butter", "black pepper"],
        "instructions": "Flake drained tuna and season with pepper. Layer onto sliced bread with cheddar cheese. Butter the exterior and toast on both sides in a skillet until cheese is melted.",
        "image": "https://www.themealdb.com/images/media/meals/1548772327.jpg",
        "source": "https://en.wikipedia.org/wiki/Melt_sandwich",
    },
    {
        "title": "Garlic Butter Skillet Chicken",
        "category": "Savory Meals Only",
        "cuisine": "American",
        "ingredients": ["chicken", "garlic", "butter", "salt", "black pepper", "olive oil"],
        "instructions": "Sear seasoned chicken in olive oil until golden. Lower heat, toss in minced garlic and generous butter, spooning melted garlic butter continuously over chicken until fully cooked.",
        "image": "https://www.themealdb.com/images/media/meals/020z181619788503.jpg",
        "source": "https://en.themealdb.com",
    },
    {
        "title": "Quick Creamy Tomato Pasta",
        "category": "Savory Meals Only",
        "cuisine": "Italian",
        "ingredients": ["pasta", "canned tomatoes", "heavy cream", "garlic", "parmesan", "olive oil"],
        "instructions": "Cook pasta until al dente. Simmer garlic and crushed tomatoes in olive oil, stir in heavy cream to form a pink sauce, and toss pasta with parmesan.",
        "image": "https://www.themealdb.com/images/media/meals/wxywrq1468235067.jpg",
        "source": "https://en.wikipedia.org/wiki/Pasta",
    }
]


def normalize_token(text):
    clean = text.lower().strip()
    clean = re.sub(r"[^\w\s]", "", clean)
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
    return " ".join(normalized)


EXCLUSION_RULES = {
    "egg": ["eggplant", "egg plant", "egg roll", "egg rolls"],
    "pea": ["peanut", "peanuts", "peanut butter"],
    "corn": ["cornbread", "cornstarch", "corn flour"],
}


def ingredient_matches(pantry_raw, recipe_raw):
    p_lower = pantry_raw.lower().strip()
    r_lower = recipe_raw.lower().strip()

    for staple, forbidden in EXCLUSION_RULES.items():
        if staple == p_lower or staple in p_lower.split():
            if any(bad in r_lower for bad in forbidden):
                return False

    p_norm = normalize_token(p_lower)
    r_norm = normalize_token(r_lower)

    for p_word in p_norm.split():
        if len(p_word) < 3:
            continue
        pattern = r"\b" + re.escape(p_word) + r"\b"
        if re.search(pattern, r_norm):
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
            notes.append(f"**{item.title()}**: Swap with {found}.")
        else:
            notes.append(f"**{item.title()}**: Omit if unavailable or pick up at the store.")
    return notes


def fetch_single_meal(mid):
    detail_url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={mid}"
    try:
        res = requests.get(detail_url, timeout=4)
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


def evaluate_all_sources(pantry_items, meal_filter="Savory Meals Only"):
    pantry_cleaned = [p.strip() for p in pantry_items if p.strip()]
    if not pantry_cleaned:
        return pd.DataFrame()

    results = []
    seen_titles = set()

    for item in LOCAL_PANTRY_CORPUS:
        cat = item["category"]
        if meal_filter == "Savory Meals Only" and cat == "Desserts / Baking":
            continue
        if meal_filter == "Breakfast" and cat != "Breakfast":
            continue
        if meal_filter == "Desserts / Baking" and cat != "Desserts / Baking":
            continue

        used, missed = match_recipe_ingredients(item["ingredients"], pantry_cleaned)
        if not used:
            continue

        total = len(used) + len(missed)
        pct = (len(used) / total) * 100 if total > 0 else 0
        cost = estimate_missing_cost(missed)

        seen_titles.add(item["title"].lower())
        results.append(
            {
                "title": item["title"],
                "cuisine": item["cuisine"],
                "category": cat,
                "image": item["image"],
                "recipe_link": item["source"],
                "used": used,
                "missed": missed,
                "missed_count": len(missed),
                "match_pct": round(pct, 1),
                "est_cost": cost,
            }
        )

    candidate_meals = {}
    for ing in pantry_cleaned:
        clean = normalize_token(ing).split()[0] if normalize_token(ing) else ing.lower()
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={clean}"
        try:
            r = requests.get(url, timeout=4)
            if r.status_code == 200:
                data = r.json()
                if data and data.get("meals"):
                    for m in data["meals"]:
                        mid = m["idMeal"]
                        if mid not in candidate_meals:
                            candidate_meals[mid] = m["strMeal"]
        except Exception:
            continue

    if candidate_meals:
        meal_ids = list(candidate_meals.keys())
        with ThreadPoolExecutor(max_workers=10) as executor:
            api_meals = list(executor.map(fetch_single_meal, meal_ids))

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
            pct = (len(used) / total) * 100 if total > 0 else 0
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
        ["Savory Meals Only", "Breakfast", "All Categories", "Desserts / Baking"],
        index=0,
    )

if st.button("Find Recipes", type="primary"):
    pantry_list = [x.strip() for x in ingredients_input.split(",") if x.strip()]
    if not pantry_list:
        st.warning("Please specify at least one ingredient.")
    else:
        with st.spinner("Searching kitchen staples across catalog..."):
            df = evaluate_all_sources(pantry_list, meal_filter=selected_meal_type)
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
        
        if st.session_state.page_number > total_pages:
            st.session_state.page_number = total_pages
        if st.session_state.page_number < 1:
            st.session_state.page_number = 1

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

                with col_details:
                    st.subheader(meal["title"])
                    st.caption(f"{meal['cuisine']} cuisine · {meal['category']}")

                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        if meal["missed_count"] == 0:
                            st.write("**Status:** 100% Match (Pantry Ready)")
                        else:
                            st.write(
                                f"**Match:** {meal['match_pct']}% ({meal['missed_count']} missing items)"
                            )
                    with col_m2:
                        if meal["missed_count"] == 0:
                            st.write("**Estimated Grocery Cost:** $0.00")
                        else:
                            st.write(
                                f"**Estimated Grocery Cost:** ~${meal['est_cost']:.2f}"
                            )

                    used_str = ", ".join(meal["used"]) if meal["used"] else "None"
                    st.write(f"**In your pantry:** {used_str}")

                    missed_str = ", ".join(meal["missed"]) if meal["missed"] else "None"
                    st.write(f"**Missing items:** {missed_str}")

                    with st.expander("Substitution Guidance and Instructions"):
                        subs = get_substitute_notes(meal["missed"])
                        for s in subs:
                            st.write(s)
                        st.link_button("Open Instructions and Video", meal["recipe_link"])

        st.write("---")
        _, col_nav_left, col_nav_input, col_nav_right, _ = st.columns([2, 0.6, 1.4, 0.6, 2])

        with col_nav_left:
            if st.button("<", disabled=(curr_page <= 1), use_container_width=True):
                st.session_state.page_number = curr_page - 1
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
            if st.button(">", disabled=(curr_page >= total_pages), use_container_width=True):
                st.session_state.page_number = curr_page + 1
                st.rerun()
