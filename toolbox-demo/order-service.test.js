import { calculateRefund, getOrderForUser } from "./order-service.js";

describe("order service", () => {
  it("returns an order", async () => {
    const order = { id: "order-7", userId: "user-a", total: 48 };
    const db = { orders: { findById: async () => order } };

    await expect(getOrderForUser(db, order.id, order.userId)).resolves.toEqual(order);
  });

  it("throws when order belongs to a different user", async () => {
    const order = { id: "order-7", userId: "user-a", total: 48 };
    const db = { orders: { findById: async () => order } };

    await expect(getOrderForUser(db, order.id, "user-b")).rejects.toThrow("Forbidden");
  });

  it("calculates a refund", () => {
    expect(calculateRefund([{ price: 12, quantity: 2 }])).toBe(24);
  });

  it("throws on negative price", () => {
    expect(() => calculateRefund([{ price: -1, quantity: 2 }])).toThrow("Invalid price");
  });

  it("throws on negative quantity", () => {
    expect(() => calculateRefund([{ price: 10, quantity: -3 }])).toThrow("Invalid quantity");
  });
});
