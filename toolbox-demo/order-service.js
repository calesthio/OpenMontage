export async function getOrderForUser(db, orderId, userId) {
  const order = await db.orders.findById(orderId);

  if (!order) {
    throw new Error("Order not found");
  }

  if (order.userId !== userId) {
    throw new Error("Order not found");
  }

  return order;
}

export function calculateRefund(items) {
  return items.reduce((total, item) => {
    if (!Number.isFinite(item.price) || !Number.isInteger(item.quantity)) {
      throw new TypeError("Refund items require a numeric price and integer quantity");
    }

    if (item.price < 0 || item.quantity < 0) {
      throw new RangeError("Refund items cannot contain negative values");
    }

    return total + item.price * item.quantity;
  }, 0);
}
