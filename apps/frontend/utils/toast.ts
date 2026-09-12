import {
    isValidElement,
    type ReactNode,
} from "react";
import {
    toast as sonnerToast,
} from "sonner";

import {
    toDisplayMessage,
} from "@/utils/apiError";

type ToastContent = Parameters<
    typeof sonnerToast
>[0];

type ToastOptions = Parameters<
    typeof sonnerToast
>[1];

function normalizeContent(
    value: unknown,
    fallback: string,
): ToastContent {
    if (isValidElement(value)) {
        return value;
    }

    if (
        typeof value === "string" ||
        typeof value === "number"
    ) {
        return value;
    }

    if (typeof value === "function") {
        const render = value as () => ReactNode;

        return (() =>
            normalizeContent(
                render(),
                fallback,
            )) as ToastContent;
    }

    return toDisplayMessage(
        value,
        fallback,
    );
}

function normalizeOptions<T>(
    options: T,
): T {
    if (
        !options ||
        typeof options !== "object"
    ) {
        return options;
    }

    const current = options as T & {
        description?: unknown;
    };

    if (
        current.description === undefined ||
        current.description === null
    ) {
        return options;
    }

    return {
        ...current,
        description: normalizeContent(
            current.description,
            "Additional information is unavailable.",
        ),
    } as T;
}

function safeToast(
    message: unknown,
    options?: ToastOptions,
) {
    return sonnerToast(
        normalizeContent(
            message,
            "Notification",
        ),
        normalizeOptions(options),
    );
}

const methods = {
    success(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.success
        >[1],
    ) {
        return sonnerToast.success(
            normalizeContent(
                message,
                "Operation completed successfully.",
            ),
            normalizeOptions(options),
        );
    },

    error(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.error
        >[1],
    ) {
        return sonnerToast.error(
            normalizeContent(
                message,
                "The operation could not be completed.",
            ),
            normalizeOptions(options),
        );
    },

    info(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.info
        >[1],
    ) {
        return sonnerToast.info(
            normalizeContent(
                message,
                "Information",
            ),
            normalizeOptions(options),
        );
    },

    warning(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.warning
        >[1],
    ) {
        return sonnerToast.warning(
            normalizeContent(
                message,
                "Please review this action.",
            ),
            normalizeOptions(options),
        );
    },

    loading(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.loading
        >[1],
    ) {
        return sonnerToast.loading(
            normalizeContent(
                message,
                "Please wait…",
            ),
            normalizeOptions(options),
        );
    },

    message(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.message
        >[1],
    ) {
        return sonnerToast.message(
            normalizeContent(
                message,
                "Notification",
            ),
            normalizeOptions(options),
        );
    },
};

/**
 * A Sonner-compatible toast function that guarantees object and FastAPI
 * validation payloads are converted to renderable text before reaching React.
 */
type SafeToast = Omit<
    typeof sonnerToast,
    | "success"
    | "error"
    | "info"
    | "warning"
    | "loading"
    | "message"
> & {
    (
        message: unknown,
        options?: ToastOptions,
    ): ReturnType<typeof sonnerToast>;

    success(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.success
        >[1],
    ): ReturnType<typeof sonnerToast.success>;

    error(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.error
        >[1],
    ): ReturnType<typeof sonnerToast.error>;

    info(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.info
        >[1],
    ): ReturnType<typeof sonnerToast.info>;

    warning(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.warning
        >[1],
    ): ReturnType<typeof sonnerToast.warning>;

    loading(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.loading
        >[1],
    ): ReturnType<typeof sonnerToast.loading>;

    message(
        message: unknown,
        options?: Parameters<
            typeof sonnerToast.message
        >[1],
    ): ReturnType<typeof sonnerToast.message>;
};

export const toast: SafeToast = Object.assign(
    safeToast,
    sonnerToast,
    methods,
) as SafeToast;
