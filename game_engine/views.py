from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import F

from rest_framework import viewsets
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action

from game_engine.models import Match, User, UserCode, MatchResult, UserPerformance
from game_engine.serializers import UserSerializer, MatchSerializer, UserCodeSerializer, UserPerformanceSerializer
from game_engine.serializers import MatchResultSerializer

import random
import os
from trueskill import Rating, rate


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    # permission_classes = [permissions.IsAuthenticated]

    @action(detail=True)
    def user_code_list(self, request, pk=None):
        objects = UserCode.objects.filter(user_id=pk)
        if objects.count() == 0:
            return Response(None, status=status.HTTP_204_NO_CONTENT)
        serializer = UserCodeSerializer(objects, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, permission_classes=[])
    def latest_code(self, request, pk=None):
        user_code = UserCode.objects.filter(user=pk)
        if user_code.exists():
            latest_code = user_code.latest("commit_time")
            resp = HttpResponse(latest_code.source_code.file, content_type="application/octet-stream")
            resp['Content-Disposition'] = f'attachment; filename={os.path.basename(latest_code.source_code.name)}'
            return resp
        return Response(status=status.HTTP_404_NOT_FOUND)  # this should not happen to the game runner (matchmaking)

    @action(detail=True)
    def performance_list(self, request, pk=None):
        objects = UserPerformance.objects.filter(user_id=pk)
        if objects.count() == 0:
            return Response(None, status=status.HTTP_204_NO_CONTENT)
        serializer = UserPerformanceSerializer(objects, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True)
    def user_match_list(self, request, pk=None):
        objects = MatchResult.objects.filter(players__contains=pk).order_by('-time_finished')
        if objects.count() == 0:
            return Response(None, status=status.HTTP_204_NO_CONTENT)
        serializer = MatchResultSerializer(objects, many=True, context={'request': request})
        return Response(serializer.data)


# todo: much needed unit tests pls ty
class MatchViewSet(viewsets.ModelViewSet):
    queryset = Match.objects.all()
    serializer_class = MatchSerializer
    permission_classes = [permissions.IsAuthenticated]

    # noinspection PyUnusedLocal,PyShadowingBuiltins
    @action(methods=["POST"], detail=True, permission_classes=[])
    def report_match(self, request, pk=None, format=None):  # todo: turn into serializer
        try:
            match = Match.objects.get(pk=pk)
        except Match.DoesNotExist:
            return Response({"ok": False, "message": "Match has been timed out"}, status=status.HTTP_410_GONE)

        if "winners" in request.data and isinstance(request.data["winners"], list):
            match_players = match.players
            winners = request.data["winners"]
            losers = set(match_players).difference(set(winners))
            if set(winners).issubset(set(match_players)):
                if "match_history" in request.data and isinstance(request.data["match_history"], list):
                    match_result = MatchResult()
                    match_result.time_started = match.allocated
                    match_result.players = Match.objects.get(pk=pk).players
                    match_result.winners = request.data["winners"]
                    match_result.match_events = request.data["match_history"]
                    match_result.save()

                    match.delete()

                    rating_group = []  # list of player ratings and their win/loss pos
                    ranks = []

                    for player in match_players:
                        up_instance, created = UserPerformance.objects.get_or_create(user=User.objects.get(pk=player))
                        up_instance.games_played += 1
                        up_instance.save()

                        # pull player elo and confidence amounts
                        player_elo = up_instance.mmr
                        player_confidence = up_instance.confidence

                        rating = Rating(float(player_elo), float(player_confidence))
                        rating_group.append([rating])
                        if player in winners:  # 0 is a winning player
                            ranks.append(0)
                        else:
                            ranks.append(1)

                    new_ratings = rate(rating_group, ranks)  # generate new elos based on trueskill

                    for player in match_players:  # update every player with their new elos
                        up_instance = UserPerformance.objects.get(user__pk=player)
                        player_rating = new_ratings.pop(0)[0]  # needs two layers to index -> team -> player
                        up_instance.mmr = player_rating.mu
                        up_instance.confidence = player_rating.sigma
                        up_instance.save()

                    # UserPerformance.objects.filter(user__pk__in=match_players).update(games_played=F('games_played')+1)
                    # UserPerformance.objects.filter(user__pk__in=winners).update(mmr=F('mmr') + 100)
                    # UserPerformance.objects.filter(user__pk__in=losers).update(mmr=F('mmr') - 100)

                    UserCode.objects.filter(user__pk__in=match_players).update(is_in_game=False)
                    # todo: implement actual MMR calculation
                    return Response(status=status.HTTP_201_CREATED)
                return Response({"ok": False, "message": "Missing match history"},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response({"ok": False, "message": "One or more winner not part of match"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": False, "message": "No winners provided"},
                        status=status.HTTP_400_BAD_REQUEST)


# noinspection PyMethodMayBeStatic
class MatchProvider(viewsets.ViewSet):
    def list(self, request):
        available_matches = Match.objects.filter(allocated__isnull=True, in_progress=False, over=False)
        if available_matches.count() > 0:
            match = random.choice(available_matches)
            match.allocated = timezone.now()  # prevents another request from getting the same match
            match.in_progress = True
            match.save()
            serializer = MatchSerializer(match)
            return JsonResponse(serializer.data)
        return Response(None, status=status.HTTP_204_NO_CONTENT)


class UserCodeViewSet(viewsets.ModelViewSet):
    queryset = UserCode.objects.all()
    serializer_class = UserCodeSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserPerformanceViewSet(viewsets.ModelViewSet):
    queryset = UserPerformance.objects.all()
    serializer_class = UserPerformanceSerializer
    permission_classes = []


class MatchResultViewSet(viewsets.ModelViewSet):
    queryset = MatchResult.objects.all()
    serializer_class = MatchResultSerializer
    # permission_classes = [permissions.IsAuthenticated]
