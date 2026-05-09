import Image from "next/image"

interface Props {
  size?: number
  className?: string
}

export function SamoyedAvatar({ size = 32, className = "" }: Props) {
  return (
    <Image
      src="/samoyed.jpg"
      width={size}
      height={size}
      alt="Cooper"
      priority
      className={`rounded-full object-cover ${className}`}
      style={{ width: size, height: size }}
    />
  )
}
