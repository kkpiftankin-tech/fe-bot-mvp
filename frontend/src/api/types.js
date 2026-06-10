// Типы, отражающие схемы из backend (schemas/ + api/setup/dto.py).
// При смене backend контракта обновлять здесь.
export class ApiError extends Error {
    status;
    body;
    constructor(status, message, body) {
        super(message);
        this.status = status;
        this.body = body;
    }
}
