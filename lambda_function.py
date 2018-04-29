"""
This sample demonstrates a simple skill built with the Amazon Alexa Skills Kit.
The Intent Schema, Custom Slots, and Sample Utterances for this skill, as well
as testing instructions are located at http://amzn.to/1LzFrj6

For additional samples, visit the Alexa Skills Kit Getting Started guide at
http://amzn.to/1LGWsLG
"""

# from __future__ import print_function

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import json


dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('StimulusSkillDB')

def get_names(userID):
    names = ""

    response = table.query(
        KeyConditionExpression=Key('UserID').eq(userID)
    )

    nameCount = len(response['Items'])
    for idx, item in enumerate(response['Items']):
        names += item['Name']
        if idx == nameCount - 2:
            names += " and "
        elif idx != nameCount - 1:
            names += ", "

    return names, nameCount

def get_name_list(userID):
    names, number = get_names(userID)
    if number == 0:
        return "There is no-one here in the house."
    elif number == 1:
        return names + " is the only person here in the house."
    else:
        return names + " are here in the house."
        
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
        response = table.put_item(
           Item=item
        ) 
    except ClientError as e:
        print(e.response)
        return e.response['Error']['Code']        
        
    return None

def delete_name(userID, name):
    try:
        response = table.delete_item(
           Key={
                'UserID': userID,
                'Name': name
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
                'ssml': output
            }
        else:
            result["outputSpeech"] = {
                'type': 'PlainText',
                'text': output
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


# --------------- Audio player required stuff ----------------------------------
# def handle_pause_request(intent, session):
# def handle_resume_request(intent, session):
# def handle_loop_off_request(intent, session):
# def handle_loop_on_request(intent, session):
# def handle_next_request(intent, session):
# def handle_prev_request(intent, session):
# def handle_repeat_request(intent, session):
# def handle_shuf_off_request(intent, session):
# def handle_shuf_on_request(intent, session):
# def handle_start_over_request(intent, session):

# --------------- Functions that control the skill's behavior ------------------

# ==========================
# Constants
CHECKIN_REFRESH_PRIORITIES = "CHECKIN_REFRESH_PRIORITIES"
CHECKIN_KEEP_OR_REPLACE_FOCUS = "CHECKIN_KEEP_OR_REPLACE_FOCUS"
NO_QUESTION = "_"

PRIORITIES = "PRIORITIES"
REFLECTION = "REFLECTION"
MEDITATION = "MEDITATION"
STRETCHING = "STRETCHING"
DONE = "DONE"
MORNING_ORDER = [MEDITATION,STRETCHING,PRIORITIES]
EVENING_ORDER = [REFLECTION,PRIORITIES,MEDITATION]

# For reset purposes only, do not modify
DEFAULT_STATE = {
    "question":NO_QUESTION,
    "evening_routine_before_priorities":"<speak></speak>",
    "evening_routine_after_priorities":"<speak></speak>",
    "morning_routine":"<speak></speak>",
    "morning_routine_elicit_index":0,
    "evening_routine_elicit_index":0,
    "morning_order_partial": [],
    "evening_order_partial": [],
}

# Create modifiable copy
state = {}
for key in DEFAULT_STATE:
    state[key] = DEFAULT_STATE[key]
#=========================

def store_thing():
    add_info("asdfasdf","STUFF")

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
        
def get_main_focus_intent_response(intent, session, state):
    session_attributes = {}
    speech_output = "This is the main focus intent."
    return build_response(session_attributes, build_speechlet_response(
        output=speech_output))
        
#================================
# Helpers

def reset_state(state):
    for key in DEFAULT_STATE:
        state[key] = DEFAULT_STATE[key]
    

# TODO: randomize agreements from alexa


def concatTexts(a,b):
    aStrip = a.strip()
    bStrip = b.strip()
    aNoTag = aStrip[7:-8] if aStrip[:7] == "<speak>" else aStrip
    bNoTag = bStrip[7:-8] if bStrip[:7] == "<speak>" else bStrip
    return "<speak>"+aNoTag+" "+bNoTag+"</speak>"
    
    
#========================
# Changing routine order methods
def set_morning_routine_intent(intent, session, state):
    # TODO: implement echo show/spot screen interaction here?
    # Each of the slots can take one of the activities available or a "done" synonym
    # Find the last fulfilled slot; finish if it says "done" or dialogState is COMPLETED
    
    # Must match slot names in morning routine intent
    slots = ["first","second","third"]
    curr_index = state["morning_routine_elicit_index"]

    # Stop if last response was "DONE"
    # Advance to next slot if last response was valid
    if "resolutions" in intent["slots"][slots[curr_index]]:
        resolution = intent["slots"][slots[curr_index]]["resolutions"]["resolutionsPerAuthority"][0]
        if resolution["status"]["code"] == "ER_SUCCESS_MATCH":
            activity = resolution["values"][0]["value"]["name"].upper()
            
            # Stop if last response was DONE and we have at least one thing
            if activity == DONE and curr_index > 0:
                MORNING_ORDER = state["morning_order_partial"]
                speech_output = "Okay, sounds good. I've updated your morning routine to " + (",".join([a.lower() for a in MORNING_ORDER]))
                
                return build_response({}, build_speechlet_response(
                    output=speech_output, should_end_session=True))
            
            # If last response was DONE at the beginning, do nothing
            # Otherwise, proceed with gathering the rest
            if not (activity == DONE and curr_index == 0):
                state["morning_routine_elicit_index"] += 1
                curr_index = state["morning_routine_elicit_index"]
                # Values in JSON schema must match constants for activities in lambda function
                state["morning_order_partial"] += [activity]
    
    # Reprompt user if the last response was invalid
    
    # TODO: tailor output speech better to the currently chosen activities
    speech_output = None
    if curr_index == 0:
        speech_output = "What do you want to do first?"
    elif curr_index == 1:
        speech_output = "What do you want to do second, or is that all?"
    elif curr_index == 2:
        speech_output = "What do you want to do third, or is that all?"
    
    return build_response({}, build_elicit_response(
        slot_to_elicit=slots[curr_index], output=speech_output))
    
    # if "value" not in intent["slots"][slot_to_elicit]:
    #     speech_output = "Sure. What's your main focus for tomorrow?"
    #     return build_response({}, build_delegate_response()))
    # else:
    #     print("WANT TO STORE THIS: "+str(intent))
    #     add_info({
    #         "userId": session["user"]["userId"],
    #         "mainFocus":intent["slots"][slot_to_elicit]["value"]
    #     })
    #     set_current_question(NO_QUESTION)
    #     prepend = "Sounds good. I'll make a note of that." # TODO: make a card in alexa app for this?
        
    #     # Execute everything after the priorities, and end the session
    #     return get_ending_evening_routine(prepend, state)
    
def set_evening_routine_intent(intent, session, state):
    pass
    
#========================
# Morning routine parts

def get_morning_meditation_script():
    speech_output = "Here is some meditation."
    return speech_output

def get_morning_stretching_script():
    speech_output = "Here is some stretching."
    return speech_output
    
def get_morning_priorities_script(userId):
    storedMainFocus = get_info(userId)[0]["mainFocus"]
    speech_output = "Your main focus for the day is " + storedMainFocus + "."
    return speech_output
    

#========================
# Morning routine methods

def get_morning_routine(state):
    intro = "Good morning!" # TODO: add name here?
    outro = "All right, we're ready to start the day! I'll catch up with you in the evening."
    speech_output = concatTexts(concatTexts(intro, state["morning_routine"]), outro)
    return build_response({},
    build_speechlet_response(output=speech_output, should_end_session=True))

def execute_morning_routine_intent(session, state):
    routineTexts = {
        MEDITATION: get_morning_meditation_script(),
        STRETCHING: get_morning_stretching_script(),
        PRIORITIES: get_morning_priorities_script(session["user"]["userId"]) #TODO: This will fail if user has never used skill before
    }
    # All of these keys must exist in the morning order list

    reset_state(state)
    
    # Build morning routine
    for activity in MORNING_ORDER:
        state["morning_routine"] = concatTexts(state["morning_routine"],routineTexts[activity])
        
    return get_morning_routine(state)





#=============
# Evening routine parts
def get_evening_reflection_script(): # TODO: make this different if you had a bad day?
    speech_output = \
    """<speak>
        Think about something that happened today that you’re grateful for.
    </speak>"""
    #<audio src="https://s3.amazonaws.com/stimulus-assets/brownnoise_30.mp3" />

    
    """Think about something that could have gone better today, and then think about how you could learn from that experience.
        <audio src="https://s3.amazonaws.com/stimulus-assets/brownnoise_30.mp3" />
        Think about how you helped others feel good today, and how you can keep considering them in the future.
        <audio src="https://s3.amazonaws.com/stimulus-assets/brownnoise_30.mp3" />
        Great.
        """
    return speech_output
    
def get_evening_meditation_script():
    speech_output = "This is some meditation."
    return speech_output
    
def get_evening_priorities_script():
    return "Did you make progress on your priorities today?"







#========================
# Evening routine methods

def get_beginning_evening_routine(state):
    intro = "Good evening. "
    speech_output = concatTexts(intro, state["evening_routine_before_priorities"])
    return build_response({}, 
    build_speechlet_response(output=speech_output))

def get_ending_evening_routine(prepend, state):
    outro = "We're all done for today. Get a good night's rest tonight, and I'll catch up with you in the morning!"
    speech_output = concatTexts(concatTexts(prepend, state["evening_routine_after_priorities"]), outro)
    return build_response({}, build_speechlet_response(output=speech_output, should_end_session=True))

def execute_evening_routine_intent(session, state):
    routineTexts = {
        REFLECTION: get_evening_reflection_script(),
        MEDITATION: get_evening_meditation_script(),
        PRIORITIES: get_evening_priorities_script()
    }
    # All of these keys must exist in the evening order list
    
    reset_state(state)
    
    prioritiesIndex = EVENING_ORDER.index(PRIORITIES) # TODO: what if user doesn't add priorities to routine?
    
    # Build everything up to and including the priorities question
    for i in range(prioritiesIndex+1):
        state["evening_routine_before_priorities"] = concatTexts(state["evening_routine_before_priorities"],routineTexts[EVENING_ORDER[i]])
        
    print("BEFORE: "+state["evening_routine_before_priorities"])
    # Build everything after the priorities question
    for i in range(prioritiesIndex+1,len(EVENING_ORDER)):
        state["evening_routine_after_priorities"] = concatTexts(state["evening_routine_after_priorities"],routineTexts[EVENING_ORDER[i]])
    print("AFTER: "+state["evening_routine_after_priorities"])
        
    state["question"] = CHECKIN_REFRESH_PRIORITIES
    # print(build_response({}, 
    # build_speechlet_response(output=speech_output)))
    # return build_response({}, 
    # build_speechlet_response(output=speech_output))
    return get_beginning_evening_routine(state)


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
            print("WANT TO STORE THIS: "+str(intent))
            add_info({
                "userId": session["user"]["userId"],
                "mainFocus":intent["slots"][slot_to_elicit]["value"]
            })
            state["question"] = NO_QUESTION
            prepend = "Sounds good. I'll make a note of that." # TODO: make a card in alexa app for this?
            
            # Execute everything after the priorities, and end the session
            return get_ending_evening_routine(prepend, state)
    
    raise ValueError("Question value expected: "+CHECKIN_KEEP_OR_REPLACE_FOCUS+", got: "+state["question"])
#=========================================
    
# Determine what to do with this intent based on where we are in the session
def handle_yes_intent(intent, session, state):
    if state["question"] == CHECKIN_REFRESH_PRIORITIES:
        state["question"] = NO_QUESTION
        speech_output = "Great work today! Do you want to keep it the same or set a new one?"
        state["question"] = CHECKIN_KEEP_OR_REPLACE_FOCUS
        return build_response({}, build_speechlet_response(
            output=speech_output))
    else:
        speech_output = "Sorry, I'm not sure about that."
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
        speech_output = "Sorry, I'm not sure about that."
        return build_response({}, build_speechlet_response(
            output=speech_output))

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
    # Dispatch to your skill's launch
    
    # Get user time from API
    
    ########################################
    ########################################
    ########################################
    
    # return execute_morning_routine_intent(session, state)
    return execute_evening_routine_intent(session, state)


def on_intent(intent_request, session, state):
    """ Called when the user specifies an intent for this skill """

    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']
    
    handlers = {
        "GetMainFocusIntent": get_main_focus_intent_response,
        "CheckinKeepMainFocusIntent": keep_main_focus_intent,
        "CheckinReplaceMainFocusIntent": replace_main_focus_intent,
        "SetMorningRoutineIntent": set_morning_routine_intent,
        "SetEveningRoutineIntent": set_evening_routine_intent,
        "AMAZON.YesIntent": handle_yes_intent,
        "AMAZON.NoIntent": handle_no_intent,
        "AMAZON.CancelIntent": handle_session_end_request,
        "AMAZON.StopIntent": handle_session_end_request,
    }
    
    try:
        return handlers[intent_name](intent, session, state)
    except Exception as e:
        # This exception probably came from inside a handler
        print(e)
        raise ValueError("Invalid intent: "+intent_name)
    
    
    
    ######################
    # Dispatch to your skill's intent handlers
    # if intent_name == "MyColorIsIntent":
    #     return set_color_in_session(intent, session)
    # elif intent_name == "WhatsMyColorIntent":
    #     return get_color_from_session(intent, session)
    if intent_name == "GetMainFocusIntent":
        return get_main_focus_intent_response(intent, session)
    # elif intent_name == "AddReminderIntent":
    #     return add_reminder_intent_response(intent, session)
    elif intent_name == "ExecuteEveningRoutineIntent":
        return execute_evening_routine_intent(session, state)
    # elif intent_name == "CheckinRefreshPrioritiesIntent":
    #     return refresh_priorities_intent(intent, session)
    # elif intent_name == "CheckinRefreshRemindersIntent":
    #     return refresh_reminders_intent(intent, session)
    elif intent_name == "CheckinKeepMainFocusIntent":
        return keep_main_focus_intent(intent, session)
    elif intent_name == "CheckinReplaceMainFocusIntent":
        return replace_main_focus_intent(intent, session)
    elif intent_name == "AMAZON.YesIntent":
        return handle_yes_intent(intent, session)
    elif intent_name == "AMAZON.NoIntent":
        return handle_no_intent(intent, session)
    elif intent_name == "AMAZON.HelpIntent":
        # return get_welcome_response()
        return get_help_response(intent, session)
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        return handle_session_end_request()
    else:
        raise ValueError("Invalid intent: " + intent_name)


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
