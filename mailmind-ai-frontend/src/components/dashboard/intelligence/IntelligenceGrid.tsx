import { motion } from "framer-motion";

import type {
  AISummariesData,
  FollowUpsData,
  ImportantEmailsData,
  SmartRepliesData,
} from "@/lib/dashboard/intelligenceMappers";
import { staggerContainer, staggerItem } from "@/lib/motion";

import { AISummariesCard, ImportantEmailsCard } from "./ImportantEmailsCard";
import { FollowUpsCard, SmartRepliesCard } from "./SmartRepliesCard";

interface IntelligenceGridProps {
  important: ImportantEmailsData;
  summaries: AISummariesData;
  replies: SmartRepliesData;
  followUps: FollowUpsData;
}

export function IntelligenceGrid({
  important,
  summaries,
  replies,
  followUps,
}: IntelligenceGridProps) {
  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-bold">
          <span className="text-gradient">Email Intelligence</span>
        </h2>
        <p className="mt-1 text-sm font-medium text-muted-foreground">
          What matters most in your inbox right now
        </p>
      </div>
      <motion.div
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="grid gap-5 sm:grid-cols-2 sm:items-stretch"
      >
        <motion.div variants={staggerItem} className="flex">
          <ImportantEmailsCard data={important} />
        </motion.div>
        <motion.div variants={staggerItem} className="flex">
          <AISummariesCard data={summaries} />
        </motion.div>
        <motion.div variants={staggerItem} className="flex">
          <SmartRepliesCard data={replies} />
        </motion.div>
        <motion.div variants={staggerItem} className="flex">
          <FollowUpsCard data={followUps} />
        </motion.div>
      </motion.div>
    </section>
  );
}
