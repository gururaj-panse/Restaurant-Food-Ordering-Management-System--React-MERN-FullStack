"""
Restaurant & Menu Module — service stub, EXCEPT the two order-lifecycle
methods below (get_my_restaurant_orders, update_order_status), which are
implemented as part of the Order Management & Order Lifecycle module
(Jira RFOMS-11/12/13) since they read/write the Order collection, not the
Restaurant collection. All other methods remain stubs pending RFOMS-9.

Current source: food-ordering-backend/src/controllers/MyRestaurantController.ts
(owner CRUD + image upload) and RestaurantController.ts (public discovery).
"""

from bson import ObjectId

from app.core.errors import AppError, EmptyBodyAppError, NotImplementedFeatureError
from app.repositories.order_repository import OrderRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import mongo_to_jsonable
from app.services.order_service import populate_order

# Mirrors the Order model's Mongoose `enum` — Motor/Pydantic apply no such
# constraint on their own, so it is enforced explicitly here to preserve
# the one REAL, reachable validation behavior from updateOrderStatus: an
# out-of-enum status value results in a 500 "unable to update order
# status", the same outcome Mongoose's save()-time enum validation produces
# today (caught by the controller's generic catch block).
_ORDER_STATUSES = {"placed", "paid", "inProgress", "outForDelivery", "delivered"}


class OrderOwnershipError(EmptyBodyAppError):
    """Mirrors MyRestaurantController.updateOrderStatus's `res.status(401).send()`."""

    def __init__(self):
        super().__init__(message="unauthorized", status_code=401)


class RestaurantService:
    def __init__(
        self,
        restaurant_repository: RestaurantRepository,
        order_repository: OrderRepository,
        user_repository: UserRepository,
    ):
        self._restaurants = restaurant_repository
        self._orders = order_repository
        self._users = user_repository

    # --- owner-facing (MyRestaurantController.ts) ---
    async def get_my_restaurant(self, user_id: str):
        raise NotImplementedFeatureError("GET /api/my/restaurant")

    async def create_my_restaurant(self, user_id: str, payload, image_file):
        raise NotImplementedFeatureError("POST /api/my/restaurant")

    async def update_my_restaurant(self, user_id: str, payload, image_file):
        raise NotImplementedFeatureError("PUT /api/my/restaurant")

    async def get_my_restaurant_orders(self, user_id: str):
        """Mirrors MyRestaurantController.getMyRestaurantOrders."""
        restaurant = await self._restaurants.get_by_owner(user_id)
        if not restaurant:
            return []  # confirmed: no restaurant -> [] (200), not 404

        orders = await self._orders.list_by_restaurant(str(restaurant["_id"]))
        populated = [await populate_order(o, self._restaurants, self._users) for o in orders]
        return mongo_to_jsonable(populated)

    async def update_order_status(self, user_id: str, order_id: str, status: str | None):
        """
        Mirrors MyRestaurantController.updateOrderStatus, WITH ONE FLAGGED
        FIX to its ownership check.

        Confirmed defect found while migrating: Node's check reads
        `restaurant?.user?._id.toString() !== req.userId`. `restaurant.user`
        is a plain ObjectId ref (this code path never populates it), and
        ObjectId has no `_id` property — so `.user._id` evaluates to
        `undefined`, and the immediately-following plain `.toString()`
        (not itself guarded by `?.`) throws a TypeError for EVERY order
        whose restaurant has a `user` set, i.e. essentially every real
        restaurant. That throw is caught by the surrounding try/catch and
        turned into a 500 "unable to update order status" — meaning the
        401 ownership-rejection branch is effectively unreachable in
        production today, and this endpoint currently fails for legitimate
        owners too, not just unauthorized callers.

        This is judged to be an unintentional implementation bug, not a
        deliberate business rule (unlike, e.g., the unescaped search regex
        or the no-op status filter elsewhere in this module, which are
        working-as-implemented quirks). Reproducing it here would mean
        shipping a new backend where restaurant owners can never update an
        order's status. A plain, working string comparison is implemented
        instead — flagged here rather than silently carried over, per the
        project's "never silently fix a confirmed gap" rule; recommend
        logging this as a new, higher-priority defect (current production
        impact: this endpoint does not work at all) separate from the
        general RFOMS-2 gap backlog.
        """
        if not order_id or not ObjectId.is_valid(order_id):
            raise AppError("Invalid order ID format", status_code=400)

        order = await self._orders.get_by_id(order_id)
        if not order:
            raise AppError("order not found", status_code=404)

        restaurant = await self._restaurants.get_by_id(str(order.get("restaurant")))
        restaurant_owner = str(restaurant.get("user")) if restaurant and restaurant.get("user") else None
        if restaurant_owner != user_id:
            raise OrderOwnershipError()

        if status not in _ORDER_STATUSES:
            raise AppError("unable to update order status", status_code=500)

        updated = await self._orders.update_status(order_id, status=status)
        if not updated:
            raise AppError("unable to update order status", status_code=500)

        updated_order = await self._orders.get_by_id(order_id)
        return mongo_to_jsonable(updated_order)

    # --- public discovery (RestaurantController.ts) ---
    async def get_all_cities(self):
        raise NotImplementedFeatureError("GET /api/restaurant/cities/all")

    async def get_restaurant(self, restaurant_id: str):
        raise NotImplementedFeatureError("GET /api/restaurant/:restaurantId")

    async def search_restaurants(self, city: str, query_params: dict):
        raise NotImplementedFeatureError("GET /api/restaurant/search/:city")
