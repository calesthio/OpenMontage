export async function getOrderForUser(db, orderId, userId) {
  const order = await db.orders.findById(orderId);

  if (!order) {
    throw new Error("Order not found");
  }

  if (order.userId !== userId) {
    throw new Error("Forbidden");
  }

  return order;
}

export function calculateRefund(items) {
  for (const item of items) {
    if (typeof item.price !== "number" || item.price < 0) {
      throw new Error("Invalid price");
    }
    if (typeof item.quantity !== "number" || item.quantity < 0) {
      throw new Error("Invalid quantity");
    }
  }
  return items.reduce((total, item) => total + item.price * item.quantity, 0);
}
