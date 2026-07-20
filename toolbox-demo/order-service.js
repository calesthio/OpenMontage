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
  return items.reduce((total, item) => total + item.price * item.quantity, 0);
}
