"use client";

import Image from "next/image";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";

export default function AnimatedLoader() {
    return (
        <div className="min-h-screen w-full flex items-center justify-center bg-linear-to-br from-background via-muted/30 to-background px-4">
            <Card className="w-full max-w-sm border-0 shadow-2xl rounded-3xl backdrop-blur-xl bg-background/80">
                <CardContent className="flex flex-col items-center justify-center py-12 gap-8">
                    {/* Logo + pulse ring */}
                    <div className="relative flex items-center justify-center">
                        <motion.div
                            className="absolute h-28 w-28 rounded-full border border-border"
                            animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0.15, 0.5] }}
                            transition={{
                                duration: 2,
                                repeat: Infinity,
                                ease: "easeInOut",
                            }}
                        />

                        <motion.div
                            className="absolute h-36 w-36 rounded-full border border-border/70"
                            animate={{ scale: [1, 1.3, 1], opacity: [0.35, 0.08, 0.35] }}
                            transition={{
                                duration: 2.5,
                                repeat: Infinity,
                                ease: "easeInOut",
                            }}
                        />

                        <motion.div
                            animate={{ y: [0, -6, 0] }}
                            transition={{
                                duration: 2,
                                repeat: Infinity,
                                ease: "easeInOut",
                            }}
                            className="relative z-10"
                        >
                            <Image
                                src="/ithute-solutions-mark.png"
                                alt="Logo"
                                width={90}
                                height={90}
                                priority
                                className="object-contain drop-shadow-xl"
                            />
                        </motion.div>
                    </div>

                    {/* Text */}
                    <div className="text-center space-y-2">
                        <motion.h2
                            className="text-2xl font-semibold tracking-tight"
                            initial={{ opacity: 0.6 }}
                            animate={{ opacity: [0.6, 1, 0.6] }}
                            transition={{
                                duration: 2,
                                repeat: Infinity,
                                ease: "easeInOut",
                            }}
                        >
                            Loading Dashboard
                        </motion.h2>

                        <p className="text-sm text-muted-foreground">
                            Preparing your workspace...
                        </p>
                    </div>

                    {/* Dots loader */}
                    <div className="flex items-center gap-2">
                        {[0, 1, 2].map((dot) => (
                            <motion.div
                                key={dot}
                                className="h-3 w-3 rounded-full bg-primary"
                                animate={{ y: [0, -8, 0] }}
                                transition={{
                                    duration: 0.8,
                                    repeat: Infinity,
                                    delay: dot * 0.15,
                                    ease: "easeInOut",
                                }}
                            />
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
