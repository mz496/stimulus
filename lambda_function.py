import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import json
import random


dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('StimulusSkillDB')
        
def get_info(userId):
    response = table.query(
        KeyConditionExpression=Key('userId').eq(userId)
    )
    # expr = "userId = :"+userId
    # response = table.query(KeyConditionExpression=expr)
    return response["Items"]

def add_info(item):
    # item must be a dict containing the userId key and any other k-v pairs desired
    
    try:
        if len(get_info(item["userId"])) == 0:
            response = table.put_item(
               Item=item
            )
        else:
            keys = []
            for key in item:
                if key != "userId":
                    keys += [key]
            
            # {"firstName": ":val1" ...}
            update_expr_map = {}
            for i in range(len(keys)):
                update_expr_map[keys[i]] = ":val{0}".format(i+1)
                
            # {":val1": "bob" ...}
            update_expr_attr_vals_map = {}
            for i in range(len(keys)):
                EAV_key = ":val{0}".format(i+1)
                update_expr_attr_vals_map[EAV_key] = item[keys[i]]
                
            # SET firstName = :val1, ...
            update_expr = "SET " + ", ".join(["{0} = {1}".format(key,update_expr_map[key]) for key in update_expr_map])
            print(update_expr)
            print(update_expr_attr_vals_map)
            response = table.update_item(
                Key={
                    "userId":item["userId"]
                },
                UpdateExpression=update_expr,
                ExpressionAttributeValues=update_expr_attr_vals_map
            )
    except ClientError as e:
        print(e.response)
        return e.response['Error']['Code']        
        
    return None

def delete_info(userId):
    try:
        response = table.delete_item(
          Key={
                'userId': userId,
            }
        )    
    except ClientError as e:
        print(e.response)
        return e.response['Error']['Code']        

    return None



# --------------- Helpers that build all of the responses ----------------------

def build_speechlet_response(output=None, title=None, reprompt_text=None, should_end_session=False):
    result = {}
    if output is not None:
        if output.strip()[:7] == "<speak>":
            result["outputSpeech"] = {
                'type': 'SSML',
                'ssml': compress_string(output).strip()
            }
        else:
            result["outputSpeech"] = {
                'type': 'PlainText',
                'text': compress_string(output).strip()
            }
        
    result["shouldEndSession"] = should_end_session
    
    if title is not None:
        result["card"] = {
            'type': 'Simple',
            'title': "SessionSpeechlet - " + title,
            'content': "SessionSpeechlet - " + output
        }
    if reprompt_text is not None:
        if reprompt_text.strip()[:7] == "<speak>":
            result["reprompt"] = {
                'outputSpeech': {
                    'type': 'SSML',
                    'ssml': reprompt_text
                }
            }
        else:
            result["reprompt"] = {
                "outputSpeech": {
                    "type": "PlainText",
                    "text": reprompt_text
                }
            }
    return result
    
def build_elicit_response(slot_to_elicit, output=None, title=None, reprompt_text=None, should_end_session=False):
    result = build_speechlet_response(output=output, title=title, reprompt_text=reprompt_text, should_end_session=should_end_session)
    result["directives"] = [
        {
            "type": "Dialog.ElicitSlot",
            "slotToElicit": slot_to_elicit
        }    
    ]
    return result
    
def build_delegate_response(updated_intent=None, title=None, should_end_session=False):
    result = build_speechlet_response(output=None, title=title, reprompt_text=None, should_end_session=should_end_session)
    result["directives"] = [
        {
            "type": "Dialog.Delegate",
        }
    ]
    if updated_intent is not None:
        result["directives"][0]["updatedIntent"] = updated_intent
    return result


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }

# --------------- Functions that control the skill's behavior ------------------

# ==========================
# Constants
CHECKIN_REFRESH_PRIORITIES = "CHECKIN_REFRESH_PRIORITIES"
CHECKIN_KEEP_OR_REPLACE_FOCUS = "CHECKIN_KEEP_OR_REPLACE_FOCUS"
NO_QUESTION = "_"

MORNING = "MORNING"
EVENING = "EVENING"
PRIORITIES = "PRIORITIES"
REFLECTION = "REFLECTION"
MEDITATION = "MEDITATION"
STRETCHING = "STRETCHING"
DONE = "DONE"

# INFINITIVE_REPRS[MORNING/EVENING].keys() represents set of all possible morning/evening activities
# Must be infinitive verb forms to list out e.g. "Do you want to ..."
INFINITIVE_REPRS = {
    MORNING: {
        MEDITATION: "meditate",
        STRETCHING: "do some stretches",
        PRIORITIES: "refresh your main focus for the day",
    },
    EVENING: {
        MEDITATION: "meditate",
        REFLECTION: "do some reflection",
        PRIORITIES: "review progress on your main focus",
    }
}
# Must be gerund/noun forms to list out e.g. "Your routine involves ..."
# All keys must have corresponding ones in spoken reprs
GERUND_REPRS = {
    MORNING: {
        MEDITATION: "meditation",
        STRETCHING: "stretching",
        PRIORITIES: "refreshing your main focus",
    },
    EVENING: {
        MEDITATION: "meditation",
        REFLECTION: "reflection",
        PRIORITIES: "reviewing progress on your main focus",
    }
}
# Must have the same number of activity slots for the number of keys in [SHORT_]INFINITIVE_REPRS[MORNING/EVENING]
ACTIVITY_SLOTS = {
    MORNING: ["firstMorning","secondMorning","thirdMorning"],
    EVENING: ["firstEvening","secondEvening","thirdEvening"]
}

# Default values
DEFAULT_ORDERS = {
    MORNING: [STRETCHING,MEDITATION,PRIORITIES],
    EVENING: [PRIORITIES,REFLECTION,MEDITATION]
}

# For reset purposes only, do not modify
DEFAULT_STATE = {
    "question":NO_QUESTION,
    "evening_routine_before_priorities":"<speak></speak>",
    "evening_routine_after_priorities":"<speak></speak>",
    "morning_routine":"<speak></speak>",
    "set_routine_elicit_index":0,
    "set_order_partial":[],
    "initial_DB_write":{}
}
NUM_DB_COLS = 5 # userId, firstName, mainFocus, morningRoutine, eveningRoutine

# Create modifiable copy
state = {}
for key in DEFAULT_STATE:
    state[key] = DEFAULT_STATE[key]
    
#=========================
# Default intents

def get_help_response(intent, session):
    session_attributes = {}
    speech_output = "This is the test."
    # If the user either does not reply to the welcome message or says something
    # that is not understood, they will be prompted again with this text.
    return build_response(session_attributes, build_speechlet_response(
        output=speech_output))

def get_welcome_response(intent, session):
    """ If we wanted to initialize the session to have some attributes we could
    add those here
    """

    session_attributes = {}
    card_title = "Welcome"
    speech_output = "Welcome to the Alexa Skills Kit sample. " \
                    "Please tell me your favorite color by saying, " \
                    "my favorite color is red"
    # If the user either does not reply to the welcome message or says something
    # that is not understood, they will be prompted again with this text.
    reprompt_text = "Please tell me your favorite color by saying, " \
                    "my favorite color is red."
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def handle_session_end_request(intent, session):
    card_title = "Session Ended"
    speech_output = "Thank you for trying the Alexa Skills Kit sample. " \
                    "Have a nice day! "
    # Setting this to true ends the session and exits the skill.
    should_end_session = True
    return build_response({}, build_speechlet_response(
        card_title, speech_output, None, should_end_session))
        
#=================================
# Simple getters/setters
    
def get_main_focus_intent_response(intent, session, state):
    print(get_info(session["user"]["userId"]))
    mainFocus = get_info(session["user"]["userId"])[0]["mainFocus"]
    speech_output = "Your main focus for today is {0}.".format(mainFocus)
    return build_response({}, build_speechlet_response(
        output=speech_output, should_end_session=True))
        
    # TODO: make sure this is robust against if there is no main focus i.e. firstrun
    # TODO: show this on the screen?
    
def get_routine_intent(intent, session, state, time_of_day):
    routine = get_info(session["user"]["userId"])[0][get_routine_DB_key_name(time_of_day)]
    activities_string = sequentialize([GERUND_REPRS[time_of_day][activity] for activity in routine])
    if len(routine) >= 2:
        speech_output = "Your {1} routine includes {0}, in that order.".format(
            activities_string,
            time_of_day.lower())
    else:
        speech_output = "Your {1} routine is just {0}.".format(
            activities_string,
            time_of_day.lower())
    return build_response({}, build_speechlet_response(
        output=speech_output, should_end_session=True))

def set_name_intent(intent_request, session, state):
    if intent_request["dialogState"] == "COMPLETED":
        speech_output = "Okay. I'll call you {0} from now on.".format(
            get_info(session["user"]["userId"])[0]["firstName"])
    
        return build_response({}, build_speechlet_response(
            output=speech_output, should_end_session=True))
    else:
        slot_info = intent_request["intent"]["slots"]["newFirstName"]
        
        if slot_info["confirmationStatus"] == "CONFIRMED":
            add_info({
                "userId": session["user"]["userId"],
                "firstName": slot_info["value"]
            })
        return build_response({}, build_delegate_response())

#================================
# Helpers

def reset_state(state):
    for key in DEFAULT_STATE:
        state[key] = DEFAULT_STATE[key]
    

# TODO: randomize agreements et al. from alexa

# Concatenates either PlainText or SSML (for either param) into a single SSML entity
def concatTexts(a,b):
    aStrip = a.strip()
    bStrip = b.strip()
    aNoTag = aStrip[7:-8] if aStrip[:7] == "<speak>" else aStrip
    bNoTag = bStrip[7:-8] if bStrip[:7] == "<speak>" else bStrip
    return "<speak>"+aNoTag+" "+bNoTag+"</speak>"
    
# Returns text representation of a list of items, where the last item is separated by last_joiner
def sequentialize(L, last_joiner="and"):
    if len(L) == 1:
        return L[0]
    elif len(L) == 2:
        return "{0} {1} {2}".format(L[0], last_joiner, L[1])
    else:
        return "{0}, {1} {2}".format(", ".join(L[:-1]), last_joiner, L[-1])

# Convert constant for time of day into a DB column name
def get_routine_DB_key_name(time_of_day):
    return time_of_day.lower() + "Routine"
def get_DB_key_name(slot_name):
    translation = {
        "mainFocus":"mainFocus",
        "newMainFocus":"mainFocus",
        "initialMainFocus":"mainFocus",
        "newFirstName":"firstName",
        "firstName":"firstName"
    }
    if slot_name not in translation:
        return slot_name
    else:
        return translation[slot_name]

# Convert multiple whitespaces to a single whitespace
def compress_string(s):
    return ' '.join(s.split())


#===================================
# New user
def new_user_intro(session, state):
    # Put values into DB
    speech_output = "Welcome. This is Stimulus, your morning and evening assistant. \
    I can help you stay focused and guide you through some relaxation routines in the morning and evening. \
    Hmm... I don't think you've used Stimulus before. Just ask Stimulus to set up and we'll get you up and running in no time."
    
    return build_response({}, build_speechlet_response(
        output=speech_output))

def new_user_collect_info_intent(intent_request, session, state):
    if intent_request["dialogState"] == "COMPLETED":
        morning_default_activities_string = sequentialize([GERUND_REPRS[MORNING][activity] for activity in DEFAULT_ORDERS[MORNING]])
        evening_default_activities_string = sequentialize([GERUND_REPRS[EVENING][activity] for activity in DEFAULT_ORDERS[EVENING]])
        speech_output = "Great. Start off your morning with me and I'll guide you through {0}.\
        Check back with me in the evening and I'll guide you through {1}.\
        Let me know if you want to change your routines, change your name, or get a reminder of your main focus.".format(
            morning_default_activities_string, evening_default_activities_string)
            
        initial_DB_write = {
            "userId": session["user"]["userId"],
            get_routine_DB_key_name(MORNING): DEFAULT_ORDERS[MORNING],
            get_routine_DB_key_name(EVENING): DEFAULT_ORDERS[EVENING]
        }
        for key in state["initial_DB_write"]:
            initial_DB_write[key] = state["initial_DB_write"][key]
        add_info(initial_DB_write)
            
        return build_response({}, build_speechlet_response(
            output=speech_output, should_end_session=True))
    else:
        # Store confirmed pairs one by one
        for slot_name in intent_request["intent"]["slots"]:
            slot_info = intent_request["intent"]["slots"][slot_name]
            if slot_info["confirmationStatus"] == "CONFIRMED":
                state["initial_DB_write"][get_DB_key_name(slot_name)] = slot_info["value"]
                # add_info({
                #     "userId": session["user"]["userId"],
                #     get_DB_key_name(slot_name): slot_info["value"]
                # })
        return build_response({}, build_delegate_response())


#========================
# Existing user intro
def existing_user_intro(session, state):
    user_info = get_info(session["user"]["userId"])[0]
    speech_output = """
    <speak>Welcome back, {0}! \
    To start your morning, ask Stimulus to start your day. \
    To finish your evening, tell Stimulus to ask how your day went.
    </speak>""".format(
        user_info["firstName"], user_info["mainFocus"])
    
    return build_response({}, build_speechlet_response(
        output=speech_output, should_end_session=True))



#========================
# Changing routine order methods

def get_remaining_activities_long_text(partial, full, time_of_day):
    # Takes two sets, returns a nice text rep of full-partial
    # For allowing the user to decide among remaining options when setting routine
    diff = list(full - partial)
    diff_reprs = [INFINITIVE_REPRS[time_of_day][activity] for activity in diff]
    if len(diff) >= 3:
        return """<speak>
            {3}Which would you like to do <say-as interpret-as="ordinal">{0}</say-as>{2}? You can {1}.
            </speak>""".format(
                str(len(partial)+1),
                sequentialize(diff_reprs, last_joiner="or"),
                ", or is that all" if len(partial) > 0 else "", # Cases for empty/nonempty partial list
                "Okay. " if len(partial) > 0 else ""
            )
    elif len(diff) == 2: # TODO: make this not affirmative if we failed to fill this slot
        return """<speak>
            Sure thing. You can {0} or {1} <say-as interpret-as="ordinal">{2}</say-as>. Which would you like to do, or is that all?
            </speak>""".format(
                diff_reprs[0], diff_reprs[1], str(len(partial)+1))
        # Let's assume we will always have at least 2 activities for each time of day, so we know the user can't end early here
    elif len(diff) == 1:
        return """<speak>
            No problem. Do you want to {0} to finish up, or is that all?
            </speak>""".format(diff_reprs[0])
    else:
        # Bad things happen if we get here
        return None
        
def get_final_set_routine_text(just_set_order,time_of_day):
    short_reprs = [GERUND_REPRS[time_of_day][activity] for activity in just_set_order]
    if len(short_reprs) == 1:
        return "Okay, sounds good. I've updated your {0} routine to include just {1}.".format(
            time_of_day.lower(),
            sequentialize(short_reprs))
    else:
        return "Okay, sounds good. I've updated your {0} routine to include {1}, in that order.".format(
            time_of_day.lower(),
            sequentialize(short_reprs))
        
def set_routine_intent(intent, session, state, time_of_day):
    # TODO: implement echo show/spot screen interaction here?
    # Each of the slots can take one of the activities available or a "done" synonym

    slots = ACTIVITY_SLOTS[time_of_day]
    curr_index = state["set_routine_elicit_index"]
    
    # If we just started, make sure we start fresh
    if curr_index == 0:
        state["set_order_partial"] = []

    # Stop if last response was "DONE"
    # Advance to next slot if last response was valid
    if "resolutions" in intent["slots"][slots[curr_index]]:
        resolution = intent["slots"][slots[curr_index]]["resolutions"]["resolutionsPerAuthority"][0]
        if resolution["status"]["code"] == "ER_SUCCESS_MATCH":
            activity = resolution["values"][0]["value"]["name"].upper()
            print("UPON MATCH: ",curr_index,state["set_order_partial"])
            
            # Stop if we exhausted everything, or            
            # Stop if last response was DONE and we have at least one thing
            if curr_index == len(INFINITIVE_REPRS[time_of_day].keys())-1 or activity == DONE and curr_index > 0:
                # DEFAULT_ORDERS[time_of_day] = state["set_order_partial"]
                # Add it to the list if it's not a (premature) DONE
                if activity != DONE:
                    state["set_order_partial"] += [activity]
                
                add_info({
                    "userId": session["user"]["userId"],
                    get_routine_DB_key_name(time_of_day): state["set_order_partial"]
                })
                speech_output = get_final_set_routine_text(state["set_order_partial"],time_of_day)
                # speech_output = "Okay, sounds good. I've updated your morning routine to " + (",".join([a.lower() for a in MORNING_ORDER]))
                
                state["set_routine_elicit_index"] = 0
                state["set_order_partial"] = []
                
                return build_response({}, build_speechlet_response(
                    output=speech_output, should_end_session=True))
            
            # If last response was DONE at the beginning, do nothing
            # Otherwise, proceed with gathering the rest
            if not (activity == DONE and curr_index == 0):
                # intent["slots"][slots[curr_index]]["confirmationStatus"] = "CONFIRMED"   
                state["set_routine_elicit_index"] += 1
                curr_index = state["set_routine_elicit_index"]
                # Values in JSON schema must match constants for activities in lambda function
                state["set_order_partial"] += [activity]
    
    # Reprompt user if the last response was invalid
    
    partial = set(state["set_order_partial"])
    full = set(INFINITIVE_REPRS[time_of_day].keys())
    print(partial,full)
    speech_output = get_remaining_activities_long_text(partial, full, time_of_day)

    return build_response({}, build_elicit_response(
        slot_to_elicit=slots[curr_index], output=speech_output))
    
#========================
# Morning routine parts

def get_morning_meditation_script():
    speech_output = None
    with open("meditation.txt") as f:
        speech_output = "".join(f.readlines())
    return speech_output

def get_morning_stretching_script():
    speech_output = None
    with open("stretches.txt") as f:
        speech_output = "".join(f.readlines())
    return speech_output
    
def get_morning_priorities_script(userId):
    storedMainFocus = get_info(userId)[0]["mainFocus"]
    speech_output = "Your main focus for the day is " + storedMainFocus + "."
    return speech_output
    
def get_transition_into_morning_priorities_script():
    choices = [
        "<break time='.5s'/>Now let's review your priorities for the day ahead.",
        "<break time='.5s'/>Now let's walk through your priorities for the day ahead.",
        "<break time='.5s'/>Now let's go over your priorities for the past day ahead.",
    ]
    return random.choice(choices)

def get_transition_into_stretching_script():
    choices = [
        "<break time='.5s'/>Now let's do some morning stretches.",
        "<break time='.5s'/>Now let's a bit of morning stretching.",
        "<break time='.5s'/>Now let's stretch for a few minutes.",
    ]
    return random.choice(choices)

#========================
# Morning routine methods

def get_morning_routine_intro():
    choices = [
        "Good morning, {0}!",
        "Rise and shine, {0}!",
    ]
    return random.choice(choices)
def get_morning_routine_outro():
    choices1 = [
        "<say-as interpret-as='interjection'>All righty!</say-as> We're ready to start the day.",
        "All right, we're ready to start the day!",
        "Ready to take on the world today?",
        "Let's go get stuff done!",
        "Can't wait to hear about what you accomplish today!",
        "<say-as interpret-as='interjection'>Okey dokey!</say-as> Time to start the day."
    ]
    choices2 = [
        "I'll catch up with you in the evening.",
        "Talk to you in the evening.",
        "Have a good one.",
        "Talk to you later."
    ]
    return "{0} {1}".format(random.choice(choices1), random.choice(choices2))
        

def get_morning_routine_text(first_name, state):
    intro = get_morning_routine_intro().format(first_name)
    outro = get_morning_routine_outro()
    speech_output = concatTexts(concatTexts(intro, state["morning_routine"]), outro)
    return build_response({},
    build_speechlet_response(output=speech_output, should_end_session=True))

def execute_morning_routine_intent(intent, session, state):
    routineTexts = {
        MEDITATION: get_morning_meditation_script(),
        STRETCHING: get_morning_stretching_script(),
        PRIORITIES: get_morning_priorities_script(session["user"]["userId"])
    }
    transitions = {
        MEDITATION: get_transition_into_meditation_script(),
        STRETCHING: get_transition_into_stretching_script(),
        PRIORITIES: get_transition_into_morning_priorities_script()
    }
    # All of these keys must exist in the morning order list

    reset_state(state)
    
    # Build morning routine
    user_info = get_info(session["user"]["userId"])[0]
    morning_order = user_info["morningRoutine"]
    
    # Introduce the first activity
    state["morning_routine"] = concatTexts(get_activity_intro().format(GERUND_REPRS[MORNING][morning_order[0]]), routineTexts[morning_order[0]])
    # Glue together the rest with transitions
    for activity in morning_order[1:]:
        state["morning_routine"] = concatTexts(state["morning_routine"],concatTexts(transitions[activity],routineTexts[activity]))
        
    return get_morning_routine_text(user_info["firstName"], state)




#=============
# Evening routine parts
def get_evening_reflection_script(): # TODO: make this different if you had a bad day?
    speech_output = \
    """<speak>
        Think about something that happened today that you’re grateful for.
        <audio src="https://s3.amazonaws.com/stimulus-assets/brownnoise_30.mp3" />
        Think about something that could have gone better today, and then think about how you could learn from that experience.
        <audio src="https://s3.amazonaws.com/stimulus-assets/brownnoise_30.mp3" />
        Think about how you helped others feel good today, and how you can keep considering them in the future.
        <audio src="https://s3.amazonaws.com/stimulus-assets/brownnoise_30.mp3" />
        <prosody rate="80%">Good</prosody>
        <prosody rate="70%">work.</prosody>
        <break time="3s"/>
    </speak>"""
    return speech_output
    
def get_evening_meditation_script():
    speech_output = None
    with open("meditation.txt") as f:
        speech_output = "".join(f.readlines())
    return speech_output
    
def get_evening_priorities_script():
    choices = [
        "Did you make progress on it today?",
        "Did you work toward it well today?",
        "Did your main focus go well today?"
    ]
    return random.choice(choices)
    
def get_transition_into_reflection_script():
    break_time = "<break time='1s'/>"
    prepositions = ["Now", "Next", "Moving on", "Next up"]
    choices = [
        "let's do some reflection on how your day went.",
        "let's reflect on how your day went.",
        "let's reconsider some parts of your day.",
    ]
    return "{0} {1}, {2}".format(break_time, random.choice(prepositions), random.choice(choices))
def get_transition_into_meditation_script():
    break_time = "<break time='1s'/>"
    prepositions = ["Now", "Next", "Moving on", "Next up"]
    choices = [
        "let's clear your mind for some meditation.",
        "let's spend a few minutes in meditation.",
        "let's find peace with some meditation.",
    ]
    return "{0} {1}, {2}".format(break_time, random.choice(prepositions), random.choice(choices))
def get_transition_into_evening_priorities_script():
    break_time = "<break time='1s'/>"
    prepositions = ["Now", "Next", "Moving on", "Next up"]
    choices = [
        "let's review your priorities for the past day.",
        "let's walk through your priorities for the past day.",
        "let's go over your priorities for the past day.",
    ]
    return "{0} {1}, {2}".format(break_time, random.choice(prepositions), random.choice(choices))

def get_evening_routine_intro():
    choices = [
        "Good evening, {0}!",
    ]
    return random.choice(choices)
def get_evening_routine_outro():
    choices1 = [
        "We're all done for today.",
        "That's all for now.",
        "That's all for today.",
        "<say-as interpret-as='interjection'>Whew!</say-as> What a long day.",
        "Another day under the belt."
    ]    
    choices2 = [
        "Get a good night's rest tonight, and I'll catch up with you in the morning!",
        "Have a good rest tonight, and I'll talk to you in the morning.",
        "Get some quality sleep tonight, and let's pick things up again in the morning.",
        "Sleep well tonight, and let's meet up again in the morning."
    ]
    return "{0} {1}".format(random.choice(choices1), random.choice(choices2))
    
def get_activity_intro():
    choices = [
        "First up is {0}.",
        "Let's start off with {0}.",
        "Let's start with {0}."
    ]
    return random.choice(choices)

#========================
# Evening routine methods

def get_beginning_evening_routine(first_name, state):
    intro = get_evening_routine_intro().format(first_name)
    speech_output = concatTexts(intro, state["evening_routine_before_priorities"])
    return build_response({}, 
    build_speechlet_response(output=speech_output))

def get_ending_evening_routine(prepend, state):
    outro = get_evening_routine_outro()
    speech_output = concatTexts(concatTexts(prepend, state["evening_routine_after_priorities"]), outro)
    return build_response({}, build_speechlet_response(output=speech_output, should_end_session=True))

def execute_evening_routine_intent(intent, session, state):
    routineTexts = {
        REFLECTION: get_evening_reflection_script(),
        MEDITATION: get_evening_meditation_script(),
        PRIORITIES: get_evening_priorities_script()
    }
    transitions = {
        REFLECTION: get_transition_into_reflection_script(),
        MEDITATION: get_transition_into_meditation_script(),
        PRIORITIES: get_transition_into_evening_priorities_script()
    }
    # All of these keys must exist in the evening order list
    
    reset_state(state)
    user_info = get_info(session["user"]["userId"])[0]
    stored_evening_order = user_info["eveningRoutine"]
    first_name = user_info["firstName"]

    try:
        prioritiesIndex = stored_evening_order.index(PRIORITIES)
    except:
        # Introduce the first activity
        state["evening_routine_after_priorities"] = concatTexts(get_activity_intro().format(GERUND_REPRS[EVENING][stored_evening_order[0]]), routineTexts[stored_evening_order[0]])
        # Glue together the other activites with transitions
        for activity in stored_evening_order[1:]:
            state["evening_routine_after_priorities"] = \
            concatTexts(state["evening_routine_after_priorities"],concatTexts(transitions[activity],routineTexts[activity]))
        intro = get_evening_routine_intro().format(first_name)
        return get_ending_evening_routine(intro, state)
    else:
        # Build everything up to and including the priorities question
        state["evening_routine_before_priorities"] = concatTexts(get_activity_intro().format(GERUND_REPRS[EVENING][stored_evening_order[0]]), routineTexts[stored_evening_order[0]])
        for i in range(1,prioritiesIndex+1):
            activity = stored_evening_order[i]
            state["evening_routine_before_priorities"] = \
            concatTexts(state["evening_routine_before_priorities"],concatTexts(transitions[activity],routineTexts[activity]))
            
        print("BEFORE: ",state["evening_routine_before_priorities"])
        # Build everything after the priorities question
        for i in range(prioritiesIndex+1,len(stored_evening_order)):
            activity = stored_evening_order[i]
            state["evening_routine_after_priorities"] = \
            concatTexts(state["evening_routine_after_priorities"],concatTexts(transitions[activity],routineTexts[activity]))
        print("AFTER: ",state["evening_routine_after_priorities"])
            
        state["question"] = CHECKIN_REFRESH_PRIORITIES
        return get_beginning_evening_routine(user_info["firstName"], state)


#==================================
# Request main focus info methods

def keep_main_focus_intent(intent, session, state):
    # Only trigger if we are in the right place in the session
    if state["question"] == CHECKIN_KEEP_OR_REPLACE_FOCUS:
        state["question"] = NO_QUESTION
        prepend = "Okay, I'll make tomorrow's main focus the same as today's."
        return get_ending_evening_routine(prepend, state)

    raise ValueError("Question value expected: "+CHECKIN_KEEP_OR_REPLACE_FOCUS+", got: "+state["question"])
            
def replace_main_focus_intent(intent, session, state):
    if state["question"] == CHECKIN_KEEP_OR_REPLACE_FOCUS:
        slot_to_elicit = "newMainFocus"
        
        if "value" not in intent["slots"][slot_to_elicit]:
            speech_output = "Sure. What's your main focus for tomorrow?"
            return build_response({}, build_elicit_response(
                slot_to_elicit=slot_to_elicit, output=speech_output))
        else:
            # print("WANT TO STORE THIS: "+str(intent))
            newMainFocus = intent["slots"][slot_to_elicit]["value"]
            userId = session["user"]["userId"]
            add_info({
                "userId": userId,
                "mainFocus": newMainFocus
            })
            firstName = get_info(userId)[0]["firstName"]
            state["question"] = NO_QUESTION
            prepend = "Sounds good. I'll make a note of that here: {0}'s main focus for tomorrow is {1}.".format(
                firstName, newMainFocus)
            # TODO: make a card in alexa app for this? TODO: make confirmation with user's name?
            
            # Execute everything after the priorities, and end the session
            return get_ending_evening_routine(prepend, state)
    
    raise ValueError("Question value expected: "+CHECKIN_KEEP_OR_REPLACE_FOCUS+", got: "+state["question"])
    
#=========================================
# Generic YES/NO intents    

# Determine what to do with this intent based on where we are in the session
def handle_yes_intent(intent, session, state):
    if state["question"] == CHECKIN_REFRESH_PRIORITIES:
        state["question"] = NO_QUESTION
        speech_output = "Great work today! Do you want to keep it the same or set a new one?" # TODO: speechcons to make this celebration more interesting
        state["question"] = CHECKIN_KEEP_OR_REPLACE_FOCUS
        return build_response({}, build_speechlet_response(
            output=speech_output))
    else:
        speech_output = "Sorry, I'm not sure how to interpret that."
        return build_response({}, build_speechlet_response(
            output=speech_output))

def handle_no_intent(intent, session, state):
    if state["question"] == CHECKIN_REFRESH_PRIORITIES:
        state["question"] = NO_QUESTION
        speech_output = "Sorry to hear that, but tomorrow's a new day! Do you want to keep it the same or set a new one?"
        state["question"] = CHECKIN_KEEP_OR_REPLACE_FOCUS
        return build_response({}, build_speechlet_response(
            output=speech_output))
    else:
        speech_output = "Sorry, I'm not sure how to interpret that."
        return build_response({}, build_speechlet_response(
            output=speech_output))

# TODO: fix implementations of builtin intents like stop/cancel/help

# --------------- Events ------------------

def on_session_started(session_started_request, session):
    """ Called when the session starts """

    print("on_session_started requestId=" + session_started_request['requestId']
          + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session, state):
    """ Called when the user launches the skill without specifying what they
    want
    """

    print("on_launch "+str(launch_request)+" "+str(session)+" requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    # If new or corrupted user, prompt to set up first
    userId = session["user"]["userId"]
    query_user = get_info(userId)
    if len(query_user) == 0 or \
    (len(query_user) > 0 and len(query_user[0].keys()) != NUM_DB_COLS):
        if len(query_user) > 0 and len(query_user[0].keys()) != NUM_DB_COLS:
            delete_info(userId)
            
        return new_user_intro(session, state)
        
    # For existing users, greet by name, talk about main focus, give commands to check in
    return existing_user_intro(session, state)


def on_intent(intent_request, session, state):
    """ Called when the user specifies an intent for this skill """

    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']
    
    
    # If new user, and intent is not setting up, prompt to set up first
    # If corrupted user, prompt to set up again
    userId = session["user"]["userId"]
    query_user = get_info(userId)
    print(query_user)
    if (len(query_user) == 0 and intent_name != "NewUserCollectInfoIntent") or \
    (len(query_user) > 0 and len(query_user[0].keys()) != NUM_DB_COLS):
        if len(query_user) > 0 and len(query_user[0].keys()) != NUM_DB_COLS:
            delete_info(userId)
            
        return new_user_intro(session, state)

    handlers = {
        "GetMainFocusIntent": get_main_focus_intent_response,
        "CheckinKeepMainFocusIntent": keep_main_focus_intent,
        "CheckinReplaceMainFocusIntent": replace_main_focus_intent,
        "ExecuteMorningRoutineIntent": execute_morning_routine_intent,
        "ExecuteEveningRoutineIntent": execute_evening_routine_intent,
        "AMAZON.YesIntent": handle_yes_intent,
        "AMAZON.NoIntent": handle_no_intent,
        "AMAZON.CancelIntent": handle_session_end_request,
        "AMAZON.StopIntent": handle_session_end_request,
    }
    
    # Handlers that need more arguments
    if intent_name not in handlers:
        if intent_name == "SetMorningRoutineIntent":
            return set_routine_intent(intent, session, state, MORNING)
        elif intent_name == "SetEveningRoutineIntent":
            return set_routine_intent(intent, session, state, EVENING)
        elif intent_name == "GetMorningRoutineIntent":
            return get_routine_intent(intent, session, state, MORNING)
        elif intent_name == "GetEveningRoutineIntent":
            return get_routine_intent(intent, session, state, EVENING)
        elif intent_name == "NewUserCollectInfoIntent":
            return new_user_collect_info_intent(intent_request, session, state)
        elif intent_name == "SetNameIntent":
            return set_name_intent(intent_request, session, state)
            
    try:
        return handlers[intent_name](intent, session, state)
    except Exception as e:
        # This exception probably came from inside a handler
        print(e)
        raise ValueError("Invalid intent: "+intent_name)

def on_session_ended(session_ended_request, session):
    """ Called when the user ends the session.

    Is not called when the skill returns should_end_session=true
    """
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # add cleanup logic here


# --------------- Main handler ------------------

def lambda_handler(event, context):
    """ Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    """
    Uncomment this if statement and populate with your skill's application ID to
    prevent someone else from configuring a skill that sends requests to this
    function.
    """
    # if (event['session']['application']['applicationId'] !=
    #         "amzn1.echo-sdk-ams.app.[unique-value-here]"):
    #     raise ValueError("Invalid Application ID")

    if event['session']['new']:
        on_session_started({'requestId': event['request']['requestId']},
                           event['session'])

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'], state)
    elif event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'], state)
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])


# TODO: error handling gracefully? "Sorry, I encountered an error trying to manage your data. Please try asking Stimulus to set up again."