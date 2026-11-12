# Blind adjudication sheet. Lines starting with # are comments.
# For each item, fill in two lines:
#   verdict: detected | miss | near_miss | false_alarm
#   reason: your reason in a few words (required with a verdict)
# detected: the finding is the candidate planted error; near_miss: right sentence, wrong kind
# of error; false_alarm: the finding is not a real error; miss: set the finding aside (neither
# a detection nor a false alarm). Then run `pathqc-eval adjudicate apply --dataset dev`.
