#!/usr/bin/env python

import simplejson
import sys
import os
from collections import defaultdict

import pygame

from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from twisted.protocols.basic import LineReceiver
from twisted.internet.task import LoopingCall

from lib.graphics_ctrl import Table 


class Client(Table):
    """
    Class to handle setting default screen, to check data received from the server,
    send data to the server, and handle pygame events.
    """
    def __init__(self):
        super(Client, self).__init__()
        self.turn = 0
        self.player = None
        self.hand = None
        self.deal_lock = True 
        self.dealer_bj = False
        self.player_bj = False
        self.default_scr()
        self.msg_actions = {'table_full':self.table_full,
                            'players_list':self.players,
                            'player_card':self.player_card,
                            'player_hands':self.player_hands,                
                            'dealer_start':self.dealer_hand,
                            'dealer_score':self.dealer_score,
                            'dealer_card':self.dealer_card,
                            'score':self.total_score,
                            'turn':self.player_turn
                           } 
        reactor.callLater(0.1, self.py_event) # pygame and twisted signals

    def game_messages(self, msg): 
        game_msg = simplejson.loads(msg)
        msg_type = list(game_msg.keys())[0]
        if msg_type == 'results':
            if self.player_score <= 21:
                self.results()        
            self.deal_lock = False
            self.player_bj = False
            self.dealer_bj = False
        else:
            load = game_msg[msg_type]
            self.msg_actions[msg_type](load)
            if msg_type == 'player_hands':
                self.hand = load[self.pl_key][:2]

    def players(self, player_list):  
        sorted(player_list)
        if not self.player:
            self.player = player_list[-1]
            self.pl_key = str(self.player)
        self.deal_lock = False
        self.playrlst = player_list 

    def player_turn(self, turn):
        if turn == self.player:
            self.turn = turn
            if self.player_score == 21:
                self.player_bj = True
                self.stand
        self.display_turn(turn)
        if self.player_score > 21:
            self.display_results('bust', self.pl_key)
        
    def player_hands(self, hands):
        self.default_scr()
        self.player_data = defaultdict(list)
        self.dealer_data = list()
        self.deal_lock = True 
        self.display_hands(hands)

    def player_card(self, card_msg): 
        player = list(card_msg.keys())[0]
        card = ''.join(i for i in card_msg[player])
        if player == self.pl_key:
            self.hand.append(card)
        self.display_card(card_msg)

    def show_player_bust(self):
        self.display_results('bust', self.pl_key)
        self.stand

    def total_score(self, score_msg):
        self.player_score = score_msg
        if self.player_score > 21:
            self.show_player_bust()
        elif self.player_score == 21 and self.turn == self.player: 
            if self.hand and len(self.hand) == 2: 
                self.player_bj = True
            self.stand

    def dealer_hand(self, hand):
        self.display_dealer(hand[0])
        self.dealer_hand = [hand[0]]

    def dealer_score(self, score):
        self.dealer_score = score
        if self.dealer_score == 'Blackjack':
            self.dealer_bj = True

    def dealer_card(self, card):
        self.dealer_hand.append(card[1])
        self.display_dealer_take(card)

    @property
    def deal(self):
        deal_msg = {'new_hand':None}
        deal_msg = simplejson.dumps(deal_msg)
        self.sendLine(deal_msg.encode("utf-8"))                    
        self.deal_lock = True

    @property
    def stand(self): 
        cur_players = sorted(self.playrlst)
        player_seat = cur_players.index(self.player)
        if player_seat + 1 == len(cur_players):
            dealer_msg = {'dealers_turn':None}
            dealer_msg = simplejson.dumps(dealer_msg)
            self.sendLine(dealer_msg.encode("utf-8"))
            self.turn = 0
        else:
            self.turn = cur_players[player_seat + 1]
            turn_msg = {'turn':self.turn}
            turn_msg = simplejson.dumps(turn_msg)
            self.sendLine(turn_msg.encode("utf-8"))

    @property
    def hit(self):
        if self.player_score < 21:
            hit_msg = {'player_card':self.player}
            hit_msg = simplejson.dumps(hit_msg)
            self.sendLine(hit_msg.encode("utf-8"))

    def results(self):
        if self.dealer_bj and not self.player_bj:	
            self.display_results('lose', self.pl_key)
        elif self.player_bj and not self.dealer_bj:
            self.display_results('bj', self.pl_key)
        elif self.player_bj and self.dealer_bj:
            self.display_results('tie', self.pl_key)
        elif self.dealer_score > 21:
            self.display_results('win', self.pl_key)
        elif self.dealer_score > self.player_score:
            self.display_results('lose', self.pl_key)
        elif self.dealer_score == self.player_score:
            self.display_results('tie', self.pl_key)
        elif self.dealer_score < self.player_score:
            self.display_results('win', self.pl_key)
               
    def py_event(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                reactor.stop()
                self.exit()
                return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # gets mouse coordinates if mouse clicked 
                pos = pygame.mouse.get_pos()
                if self.stand_rect.collidepoint(pos) and self.player == self.turn:
                    self.stand_click()
                    self.stand
                if self.deal_rect.collidepoint(pos) and self.deal_lock == False:
                    self.deal_click()
                    self.deal
                if self.hit_rect.collidepoint(pos) and self.player == self.turn:        
                    self.hit_click()
                    self.hit
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                pos = pygame.mouse.get_pos()
                if self.stand_rect.collidepoint(pos):
                    self.stand_unclick()
                if self.deal_rect.collidepoint(pos):
                    self.deal_unclick()
                if self.hit_rect.collidepoint(pos):
                    self.hit_unclick()

    def table_full(self, msg):
        reactor.stop()
        self.exit()
        print("Table Full")


class BlackClientProtocol(LineReceiver):
    """ 
    Class client for receiving data from the server.
    """
    def __init__(self, recv):
        self.recv = recv

    def lineReceived(self, line):
        self.recv(line)


class BlackClient(ClientFactory):
    """
    Class that builds protocol instances.
    """
    def __init__(self, client):
        self.client = client

    # builds protocol instance  
    def buildProtocol(self, addr):
        proto = BlackClientProtocol(self.client.game_messages)
        self.client.sendLine = proto.sendLine
        return proto


if __name__ == '__main__':
    c = Client()
    # LoopingCall method to keep checking 'tick' method for pygame events 
    lc = LoopingCall(c.py_event)
    lc.start(0.1)
    reactor.connectTCP('127.0.0.1', 6000, BlackClient(c))
    reactor.run()
