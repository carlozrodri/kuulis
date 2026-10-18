import { Config } from '@remotion/cli/config'

// Same output for every render: JPEG frames are faster; H.264 MP4 is what TikTok, Reels and Shorts expect.
Config.setVideoImageFormat('jpeg')
Config.setCodec('h264')
Config.setOverwriteOutput(true)
