/**
 * Saves the stack trace of a native Android crash to <filesDir>/kuulis-last-crash.txt before the app closes.
 * On the next launch src/lib/crashReport.ts sends it to POST /client-errors and deletes it, so we can see
 * why the app closed on a user's phone without a crash-reporting service. The previous handler still runs,
 * so Android shows its usual "app stopped" behaviour.
 */
const { withMainApplication } = require('expo/config-plugins');

const MARKER = 'kuulis-last-crash.txt';

const KOTLIN = `
    // Kuulis: keep the last native crash so the app can report it on the next launch (plugins/withCrashLog.js).
    val previousCrashHandler = Thread.getDefaultUncaughtExceptionHandler()
    Thread.setDefaultUncaughtExceptionHandler { thread, error ->
      try {
        val trace = android.util.Log.getStackTraceString(error)
        java.io.File(filesDir, "${MARKER}").writeText("thread=" + thread.name + "\\n" + trace.take(20000))
      } catch (_: Throwable) {
      }
      previousCrashHandler?.uncaughtException(thread, error)
    }
`;

module.exports = function withCrashLog(config) {
  return withMainApplication(config, (mod) => {
    if (mod.modResults.language !== 'kt') {
      throw new Error('withCrashLog expects a Kotlin MainApplication');
    }
    let contents = mod.modResults.contents;
    if (!contents.includes(MARKER)) {
      const anchor = 'super.onCreate()';
      if (!contents.includes(anchor)) throw new Error('withCrashLog: super.onCreate() not found in MainApplication');
      contents = contents.replace(anchor, `${anchor}\n${KOTLIN}`);
    }
    mod.modResults.contents = contents;
    return mod;
  });
};
