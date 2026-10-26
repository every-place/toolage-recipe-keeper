export type Ingredient = {
  id?: number;
  raw_text: string;
  group_label: string | null;
  quantity?: number | null;
  quantity_max?: number | null;
  unit?: string | null;
  name?: string | null;
  note?: string | null;
};

export type Step = { id?: number; text: string; photo_id: number | null; timer_minutes?: number | null };

export type Recipe = {
  id: number;
  title: string;
  source_person: string | null;
  recipe_yield: string | null;
  servings: number | null;
  prep_minutes: number | null;
  cook_minutes: number | null;
  category: string | null;
  tags: string[];
  story: string | null;
  story_year: string | null;
  notes: string | null;
  hero_photo_id: number | null;
  card_photo_id: number | null;
  ingredients: Ingredient[];
  steps: Step[];
  created_by_name?: string | null;
  updated_at?: string;
};

export type RecipeSummary = Pick<Recipe, "id" | "title" | "source_person" | "category" | "tags" | "hero_photo_id"> & {
  updated_at: string;
};

export type Template = { id?: number; group: string; text: string; custom: boolean };

export type Me = {
  user: { id: number; display_name: string; email: string; household_id: number };
  household: {
    id: number;
    name: string;
    plan: "free" | "premium";
    join_code: string;
    members: { id: number; display_name: string; email: string }[];
  };
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: "same-origin", headers: {} };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError(0, "Can't reach Recipe Keeper. Check your internet connection.");
  }
  if (!res.ok) {
    let message = `Something went wrong (${res.status}).`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = "Please check the highlighted fields.";
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  me: () => request<Me>("GET", "/api/me"),
  login: (email: string, password: string) => request("POST", "/api/auth/login", { email, password }),
  signup: (body: { email: string; password: string; display_name: string; household_name?: string; join_code?: string }) =>
    request("POST", "/api/auth/signup", body),
  logout: () => request("POST", "/api/auth/logout"),
  listRecipes: (q?: string, category?: string) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (category) params.set("category", category);
    return request<{ recipes: RecipeSummary[]; categories: string[] }>("GET", `/api/recipes?${params}`);
  },
  getRecipe: (id: number) => request<Recipe>("GET", `/api/recipes/${id}`),
  createRecipe: (r: RecipeInput) => request<Recipe>("POST", "/api/recipes", r),
  updateRecipe: (id: number, r: RecipeInput) => request<Recipe>("PUT", `/api/recipes/${id}`, r),
  deleteRecipe: (id: number) => request("DELETE", `/api/recipes/${id}`),
  parseIngredients: (text: string) => request<{ lines: Ingredient[] }>("POST", "/api/ingredients/parse", { text }),
  templates: () => request<{ templates: Template[]; slots: Record<string, string[]> }>("GET", "/api/templates"),
  addTemplate: (text: string) => request<{ id: number }>("POST", "/api/templates", { text }),
  deleteTemplate: (id: number) => request("DELETE", `/api/templates/${id}`),
  uploadPhoto: async (file: Blob) => {
    const form = new FormData();
    form.append("file", file, "photo.jpg");
    return request<{ id: number }>("POST", "/api/photos", form);
  },
};

export type RecipeInput = Omit<Recipe, "id" | "ingredients" | "steps" | "created_by_name" | "updated_at"> & {
  ingredients: { raw_text: string; group_label: string | null }[];
  steps: { text: string; photo_id: number | null }[];
};

export type Nutrients = {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  sugar_g: number;
  sodium_mg: number;
};

export type NutritionLine = {
  ingredient_id: number;
  raw_text: string;
  name: string | null;
  food_id: string | null;
  food_name: string | null;
  status: "ok" | "unmatched" | "skipped" | "no_amount" | "no_conversion";
  nutrients: Nutrients | null;
  serving?: string;
};

export type Nutrition = {
  total: Nutrients;
  per_serving: Nutrients | null;
  servings: number | null;
  lines: NutritionLine[];
  counted: number;
  needs_attention: number;
};

export type FoodResult = { food_id: string; name: string; brand: string | null; summary: string };

export const nutritionApi = {
  get: (recipeId: number) => request<Nutrition>("GET", `/api/recipes/${recipeId}/nutrition`),
  match: (recipeId: number) => request<Nutrition>("POST", `/api/recipes/${recipeId}/nutrition/match`),
  search: (q: string) => request<{ results: FoodResult[] }>("GET", `/api/nutrition/search?q=${encodeURIComponent(q)}`),
  choose: (name: string, food_id: string | null, skip = false) =>
    request("PUT", "/api/nutrition/match", { name, food_id, skip }),
};

export type MenuSummary = { id: number; name: string; created_at: string; recipe_count: number };
export type Menu = {
  id: number;
  name: string;
  recipes: { recipe_id: number; multiplier: number; title: string; hero_photo_id: number | null }[];
};
export type ShopItem = {
  key: string;
  name: string;
  amount: string;
  recipes: string[];
  aisle: string;
  state: "need" | "got" | "have";
  staple: boolean;
};
export type Shopping = {
  aisles: { aisle: string; items: ShopItem[] }[];
  counts: { need: number; got: number; have: number };
  text: string;
  menu: { id: number; name: string };
};

export const menuApi = {
  list: () => request<{ menus: MenuSummary[] }>("GET", "/api/menus"),
  create: (name: string) => request<Menu>("POST", "/api/menus", { name }),
  get: (id: number) => request<Menu>("GET", `/api/menus/${id}`),
  rename: (id: number, name: string) => request<Menu>("PATCH", `/api/menus/${id}`, { name }),
  remove: (id: number) => request("DELETE", `/api/menus/${id}`),
  setRecipe: (id: number, recipeId: number, multiplier: number) =>
    request<Menu>("PUT", `/api/menus/${id}/recipes/${recipeId}`, { multiplier }),
  shopping: (id: number) => request<Shopping>("GET", `/api/menus/${id}/shopping`),
  check: (id: number, key: string, state: ShopItem["state"] | null) =>
    request<Shopping>("PUT", `/api/menus/${id}/shopping`, { key, state }),
  reset: (id: number) => request<Shopping>("POST", `/api/menus/${id}/shopping/reset`),
  staple: (name: string, on: boolean) => request<{ staples: string[] }>("PUT", "/api/staples", { name, on }),
};

export const photoUrl = (id: number) => `/api/photos/${id}`;
